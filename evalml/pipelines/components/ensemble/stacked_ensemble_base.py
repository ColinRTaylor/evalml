"""Stacked Ensemble Base."""
from inspect import isclass

from skopt.space.space import Categorical

from evalml.model_family import ModelFamily
from evalml.pipelines.components import Estimator
from evalml.pipelines.components.estimators import (
    ElasticNetClassifier,
    XGBoostClassifier,
)
from evalml.pipelines.components.utils import handle_component_class
from evalml.utils import classproperty

_nonstackable_model_families = [ModelFamily.BASELINE, ModelFamily.NONE]


class StackedEnsembleBase(Estimator):
    """Stacked Ensemble Base Class.

    Arguments:
        final_estimator (Estimator or subclass): The estimator used to combine the base estimators.
        n_jobs (int or None): Integer describing level of parallelism used for pipelines. None and 1 are equivalent.
            If set to -1, all CPUs are used. For n_jobs greater than -1, (n_cpus + 1 + n_jobs) are used. Defaults to -1.
            - Note: there could be some multi-process errors thrown for values of `n_jobs != 1`. If this is the case, please use `n_jobs = 1`.
        random_seed (int): Seed for the random number generator. Defaults to 0.
    """

    model_family = ModelFamily.ENSEMBLE
    hyperparameter_ranges = {
        "final_estimator": Categorical([ElasticNetClassifier, XGBoostClassifier]),
        ElasticNetClassifier.name: ElasticNetClassifier.hyperparameter_ranges,
        XGBoostClassifier.name: XGBoostClassifier.hyperparameter_ranges,
    }
    """ModelFamily.ENSEMBLE"""
    _default_final_estimator = None

    def __init__(
        self,
        final_estimator=None,
        final_estimator_parameters=None,
        n_jobs=-1,
        random_seed=0,
        **kwargs,
    ):
        final_estimator = final_estimator or self._default_final_estimator()
        final_estimator_obj = handle_component_class(final_estimator)
        if isclass(final_estimator_obj) and final_estimator_parameters is not None:
            final_estimator_obj = final_estimator_obj(**final_estimator_parameters)

        parameters = {
            "final_estimator": final_estimator_obj,
            # "final_estimator_parameters": final_estimator_parameters,
            "n_jobs": n_jobs,
        }
        parameters.update(kwargs)

        super().__init__(
            parameters=parameters,
            component_obj=final_estimator_obj,
            random_seed=random_seed,
        )

    @property
    def feature_importance(self):
        """Not implemented for StackedEnsembleClassifier and StackedEnsembleRegressor."""
        raise NotImplementedError(
            "feature_importance is not implemented for StackedEnsembleClassifier and StackedEnsembleRegressor"
        )

    @classproperty
    def default_parameters(cls):
        """Returns the default parameters for stacked ensemble classes.

        Returns:
            dict: default parameters for this component.
        """
        return {
            "final_estimator": cls._default_final_estimator,
            "n_jobs": -1,
        }
