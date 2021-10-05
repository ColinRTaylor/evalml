"""Base class for the AutoML algorithms which power EvalML."""
from abc import ABC, abstractmethod

from networkx.algorithms.centrality import voterank_alg

from evalml import pipelines
from evalml.exceptions import PipelineNotFoundError
from evalml.model_family.model_family import ModelFamily
from evalml.pipelines.utils import _make_stacked_ensemble_pipeline
from evalml.tuners import SKOptTuner


class AutoMLAlgorithmException(Exception):
    """Exception raised when an error is encountered during the computation of the automl algorithm."""

    pass


class AutoMLAlgorithm(ABC):
    """Base class for the AutoML algorithms which power EvalML.

    This class represents an automated machine learning (AutoML) algorithm. It encapsulates the decision-making logic behind an automl search, by both deciding which pipelines to evaluate next and by deciding what set of parameters to configure the pipeline with.

    To use this interface, you must define a next_batch method which returns the next group of pipelines to evaluate on the training data. That method may access state and results recorded from the previous batches, although that information is not tracked in a general way in this base class. Overriding add_result is a convenient way to record pipeline evaluation info if necessary.

    Args:
        allowed_pipelines (list(class)): A list of PipelineBase subclasses indicating the pipelines allowed in the search. The default of None indicates all pipelines for this problem type are allowed.
        custom_hyperparameters (dict): Custom hyperparameter ranges specified for pipelines to iterate over.
        max_iterations (int): The maximum number of iterations to be evaluated.
        tuner_class (class): A subclass of Tuner, to be used to find parameters for each pipeline. The default of None indicates the SKOptTuner will be used.
        random_seed (int): Seed for the random number generator. Defaults to 0.
    """

    def __init__(
        self,
        allowed_pipelines=None,
        custom_hyperparameters=None,
        max_iterations=None,
        tuner_class=None,
        random_seed=0,
        n_jobs=-1,
    ):
        self.random_seed = random_seed
        self.allowed_pipelines = allowed_pipelines or []
        self.max_iterations = max_iterations
        self._tuner_class = tuner_class or SKOptTuner
        self._tuners = {}
        self._best_pipeline_info = {}
        self.text_in_ensembling = False
        self.n_jobs = n_jobs
        self._selected_cols = None
        for pipeline in self.allowed_pipelines:
            pipeline_hyperparameters = pipeline.get_hyperparameter_ranges(
                custom_hyperparameters
            )
            if pipeline.model_family == ModelFamily.ENSEMBLE:
                pipeline_flattened_hyperparameters = {}
                for (
                    component,
                    component_hyperparameters,
                ) in pipeline_hyperparameters.items():
                    component_flattened_hyperparameters = {}
                    for parameter, range in component_hyperparameters.items():
                        if isinstance(range, dict):
                            for key, value in range.items():
                                component_flattened_hyperparameters[
                                    f"{parameter}_{key}"
                                ] = value
                        else:
                            component_flattened_hyperparameters[parameter] = range
                    pipeline_flattened_hyperparameters[
                        component
                    ] = component_flattened_hyperparameters
                pipeline_hyperparameters = pipeline_flattened_hyperparameters
            self._tuners[pipeline.name] = self._tuner_class(
                pipeline_hyperparameters, random_seed=self.random_seed
            )
        self._pipeline_number = 0
        self._batch_number = 0

    @abstractmethod
    def next_batch(self):
        """Get the next batch of pipelines to evaluate.

        Returns:
            list[PipelineBase]: A list of instances of PipelineBase subclasses, ready to be trained and evaluated.
        """

    @abstractmethod
    def _transform_parameters(self, pipeline, proposed_parameters):
        """Given a pipeline parameters dict, make sure pipeline_params, custom_hyperparameters, n_jobs are set properly.

        Arguments:
            pipeline (PipelineBase): The pipeline object to update the parameters.
            proposed_parameters (dict): Parameters to use when updating the pipeline.
        """

    def add_result(self, score_to_minimize, pipeline, trained_pipeline_results):
        """Register results from evaluating a pipeline.

        Args:
            score_to_minimize (float): The score obtained by this pipeline on the primary objective, converted so that lower values indicate better pipelines.
            pipeline (PipelineBase): The trained pipeline object which was used to compute the score.
            trained_pipeline_results (dict): Results from training a pipeline.

        Raises:
            PipelineNotFoundError: If pipeline is not allowed in search.
        """
        if pipeline.name not in self._tuners:
            raise PipelineNotFoundError(
                f"No such pipeline allowed in this AutoML search: {pipeline.name}"
            )
        self._tuners[pipeline.name].add(pipeline.parameters, score_to_minimize)

    @property
    def pipeline_number(self):
        """Returns the number of pipelines which have been recommended so far."""
        return self._pipeline_number

    @property
    def batch_number(self):
        """Returns the number of batches which have been recommended so far."""
        return self._batch_number

    def _create_ensemble(self, proposed_parameters):
        # next_batch = []
        best_pipelines = list(self._best_pipeline_info.values())
        problem_type = best_pipelines[0]["pipeline"].problem_type
        n_jobs_ensemble = 1 if self.text_in_ensembling else self.n_jobs
        input_pipelines = []
        for pipeline_dict in best_pipelines:
            pipeline = pipeline_dict["pipeline"]
            pipeline_params = self._transform_parameters(
                pipeline, pipeline_dict["parameters"]
            )
            if (
                "Select Columns Transformer"
                in pipeline.component_graph.component_instances
            ):
                pipeline_params.update(
                    {"Select Columns Transformer": {"columns": self._selected_cols}}
                )
            input_pipelines.append(
                pipeline.new(parameters=pipeline_params, random_seed=self.random_seed)
            )
        # ensembler_parameters = proposed_parameters.get("Stacked Ensemble Classifier", None) or proposed_parameters.get("Stacked Ensemble Regressor", None)
        ensembler_parameters = list(proposed_parameters.values())[0]
        final_estimator = ensembler_parameters["final_estimator"]
        final_estimator_parameters = {}
        for key, value in ensembler_parameters.items():
            if key.startswith(final_estimator.name):
                estimator_key = key.replace(f"{final_estimator.name}_", "")
                final_estimator_parameters[estimator_key] = value
        ensemble = _make_stacked_ensemble_pipeline(
            input_pipelines,
            problem_type,
            final_estimator=final_estimator,
            final_estimator_parameters=final_estimator_parameters,
            random_seed=self.random_seed,
            n_jobs=n_jobs_ensemble,
        )
        return ensemble
        # next_batch.append(ensemble)
        # return next_batch
