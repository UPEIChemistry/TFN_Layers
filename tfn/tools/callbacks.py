import os
from pathlib import Path
from typing import Union

import numpy as np
import tensorflow as tf
from tensorflow.keras.callbacks import Callback
from tensorflow.keras.models import Model
from tensorflow.keras.metrics import categorical_accuracy

from .converters import ndarrays_to_xyz


class TestModel(Callback):
    def __init__(self, x_test, y_test):
        super().__init__()
        self.x_test = x_test
        self.y_test = y_test

    def on_train_end(self, logs=None):
        predictions = self.model.evaluate(x=self.x_test, y=self.y_test)
        if not isinstance(predictions, list):
            predictions = [predictions]
        for pred, name in zip(predictions, self.model.metric_names):
            logs["test_{}".format(name)] = pred


class WriteCartesians(Callback):
    def __init__(
        self,
        path: Union[str, Path],
        validation: list = None,
        test: list = None,
        max_structures: int = 5,
        write_rate: int = 100,
        tensorboard_logdir: str = None,
    ):
        """
        :param path: Base path to which .xyz files will be written to. Will create subdirectories
            at this path as needed.
        :param validation: Defaults to None. List of val data to write. Of shape [[z, r, p], [ts]].
            If None, will not write validation .xyz files.
        :param test: list. Defaults to None. Same as validation, but for test data.
        :param max_structures: int. Defaults to 10. Max number of structures to write .xyz files
            for.
        :param write_rate: int. Defaults to 50. Number of epochs to take before writing
            validation Cartesians (if validation data provided).
        """
        super().__init__()
        self.path = Path(path)
        self.validation = validation
        self.test = test
        self.max_structures = max_structures
        self.write_rate = write_rate
        logdir = tensorboard_logdir or self.path.parent / "logs"
        self.file_writer = tf.summary.create_file_writer(str(logdir / "metrics"))
        self.file_writer.set_as_default()

    def get_vectors(self, inputs):
        model = Model(
            inputs=self.model.input,
            outputs=[
                self.model.get_layer("averaged_midpoint").output,
                self.model.get_layer("ts_vectors").output,
            ],
        )
        midpoint, vectors = model.predict([np.expand_dims(a, axis=0) for a in inputs])
        return [np.squeeze(a, axis=0) for a in (midpoint, vectors)]

    def _unwrap_data_lazily(self, data: list):
        """

        :param data:
        :return:
        """
        predicted_transition_states = self.model.predict(data[0])
        ((atomic_nums, reactants, products), (true_transition_states,),) = data
        for i, (z, r, p, ts_true, ts_pred) in enumerate(
            zip(
                atomic_nums[: self.max_structures],
                reactants[: self.max_structures],
                products[: self.max_structures],
                true_transition_states[: self.max_structures],
                predicted_transition_states[: self.max_structures],
            )
        ):
            yield i, z, r, p, ts_true, ts_pred

    @staticmethod
    def mae(x, y):
        return np.mean(np.abs(x - y))

    def write_cartesians(self, data: list, path: Path):
        """
        :param data: list. Of shape [[z, r, p], [true]]
        :param path: Path object. Base path subdirectories and .xyz files will be written under.
        """
        for i, z, r, p, ts, pred in self._unwrap_data_lazily(data):
            # Write vectors
            m, vectors = self.get_vectors([z, r, p])
            vector_path = path / "vectors"
            os.makedirs(vector_path, exist_ok=True)
            np.savetxt(  # Write vectors .txt file
                vector_path / f"{i}_vectors.txt", vectors
            )
            pred_message = (
                f"mae: {self.mae(pred, ts)}  "
                f"-- largest vector component: {np.max(vectors)} "
                f"-- smallest vector component {np.min(vectors)}"
            )
            # Write files
            ndarrays_to_xyz(ts, z, path / f"true/{i}_true.xyz", f"{self.mae(ts, ts)}")
            ndarrays_to_xyz(
                pred, z, path / f"predicted/{i}_pred.xyz", pred_message,
            )
            ndarrays_to_xyz(
                m, z, path / f"midpoints/{i}_midpoint.xyz", f"{self.mae(m, ts)}",
            )
            ndarrays_to_xyz(
                r, z, path / f"reactants/{i}_reactant.xyz", f"{self.mae(r, ts)}"
            )
            ndarrays_to_xyz(
                p, z, path / f"products/{i}_product.xyz", f"{self.mae(p, ts)}"
            )

    def on_epoch_end(self, epoch, logs=None):
        if self.validation is None:
            return
        else:
            if epoch % self.write_rate == 0:
                (z, r, p), (ts,) = self.validation
                midpoint_loss = self.mae((r + p) / 2, ts)
                tf.summary.scalar("val_midpoint_loss", midpoint_loss, epoch)
                self.write_cartesians(self.validation, self.path / f"epoch_{epoch}")

    def on_train_end(self, logs=None):
        if self.test is None:
            return
        else:
            (z, r, p), (ts,) = self.validation
            midpoint_loss = self.mae((r + p) / 2, ts)
            print(f"midpoint test loss: {midpoint_loss}")
            self.write_cartesians(self.test, self.path / "test")


class ClassificationMetrics(Callback):
    def __init__(self, validation, log_dir):
        super().__init__()
        self.validation = validation
        self.val_f1s = None
        self.val_recalls = None
        self.val_precisions = None
        self.file_writer = tf.summary.create_file_writer(log_dir + "/metrics")
        self.file_writer.set_as_default()

    def on_epoch_end(self, epoch, logs=None):
        target = self.validation[1]
        prediction = np.asarray(self.model.predict(self.validation[0]))
        f1score = self.f1_score(target, prediction)
        precision = self.precision(target, prediction)
        recall = self.recall(target, prediction)
        accuracy = np.mean(categorical_accuracy(target, prediction))
        tf.summary.scalar("f1score", f1score, epoch)
        tf.summary.scalar("precision", precision, epoch)
        tf.summary.scalar("recall", recall, epoch)
        tf.summary.scalar("accuracy", accuracy, epoch)
        print(
            f"Metrics for epoch {epoch}:"
            f" -- val_f1score: {f1score} -- val_precision: {precision} -- val_recall: {recall} "
            f" -- val_accuracy: {accuracy}"
        )

    def f1_score(self, y_true, y_pred):
        recall = self.recall(y_true, y_pred)
        precision = self.precision(y_true, y_pred)
        return 2 * ((precision * recall) / (precision + recall + 1e-7))

    def recall(self, y_true, y_pred):
        true_positives = np.sum(np.round(np.clip(y_true * y_pred, 0, 1)))
        possible_positives = np.sum(np.round(np.clip(y_true, 0, 1)))
        return true_positives / (possible_positives + 1e-7)

    def precision(self, y_true, y_pred):
        true_positives = np.sum(np.round(np.clip(y_true * y_pred, 0, 1)))
        predicted_positives = np.sum(np.round(np.clip(y_pred, 0, 1)))
        return true_positives / (predicted_positives + 1e-7)
