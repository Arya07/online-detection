from abc import ABC, abstractmethod
import os
import sys
basedir = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(basedir, '..', '..')))
from py_od_utils import getFeatPath
import yaml


class RegionClassifierAbstract(ABC):
    def __init__(self, classifier, positive_selector, negative_selector, cfg_path=None):
        if cfg_path is not None:
            self.cfg = yaml.load(open(cfg_path), Loader=yaml.FullLoader)
            self.experiment_name = self.cfg['EXPERIMENT_NAME']
            self.train_imset = self.cfg['DATASET']['TARGET_TASK']['TRAIN_IMSET']
            self.test_imset = self.cfg['DATASET']['TARGET_TASK']['TEST_IMSET']
            self.classifier_options = self.cfg['ONLINE_REGION_CLASSIFIER']['CLASSIFIER']
            self.feature_folder = getFeatPath(self.cfg)
            self.mean = 0
            self.std = 0
            self.mean_norm = 0
            self.is_rpn = False
            self.lam = None
            self.sigma = None
            self.output_folder = self.cfg['OUTPUT_FOLDER']

        else:
            print('Config file path not given. cfg variable set to None.')
            self.cfg = None

        self.classifier = classifier
        self.negative_selector = negative_selector
        self.positive_selector = positive_selector
        self.num_classes = self.positive_selector.get_num_classes()
        # self.experiment_name = experiment_name

    @abstractmethod
    def loadRegionClassifier(self) -> None:
        pass

    @abstractmethod
    def trainRegionClassifier(self, dataset) -> None:
        pass

    @abstractmethod
    def testRegionClassifier(self, dataset) -> None:
        pass

    @abstractmethod
    def predict(self, dataset) -> None:
        pass
