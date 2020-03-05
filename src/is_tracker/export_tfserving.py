import time
from absl import app, flags, logging
from absl.flags import FLAGS
import cv2
import numpy as np
import tensorflow as tf
from yolov3_tf2.models import (
    YoloV3, YoloV3Tiny
)
from yolov3_tf2.dataset import transform_images

from tensorflow.python.eager import def_function
from tensorflow.python.framework import tensor_spec
from tensorflow.python.util import nest

from pprint import pprint


config = tf.compat.v1.ConfigProto()
#config.gpu_options.per_process_gpu_memory_fraction = 0.8
config.gpu_options.allow_growth = True
sess = tf.compat.v1.Session(config=config)

flags.DEFINE_string('weights', './is-tracker/etc/checkpoints/yolov3.tf',
                    'path to weights file')
flags.DEFINE_boolean('tiny', False, 'yolov3 or yolov3-tiny')
flags.DEFINE_string('output', './is-tracker/src/serving/yolov3/1', 'path to saved_model')
flags.DEFINE_string('classes', './is-tracker/etc/data/coco.names', 'path to classes file')
flags.DEFINE_string('image', './is-tracker/etc/data/Camera_1.jpg', 'path to input image')


# TODO: remove this after upstream fix
# modified from: tensorflow.python.keras.saving.saving_utils.trace_model_call
def trace_model_call(model):
    inputs = model.inputs
    input_names = model.input_names

    input_signature = []
    for input_tensor, input_name in zip(inputs, input_names):
        input_signature.append(tensor_spec.TensorSpec(
            shape=input_tensor.shape, dtype=input_tensor.dtype,
            name=input_name))

    @def_function.function(input_signature=input_signature, autograph=False)
    def _wrapped_model(*args):
        inputs = args[0] if len(input_signature) == 1 else list(args)
        outputs_list = nest.flatten(model(inputs=inputs))
        output_names = model.output_names
        return {"{}_{}".format(kv[0], i): kv[1] for i, kv in enumerate(
            zip(output_names, outputs_list))}

    return _wrapped_model


def main(_argv):
    if FLAGS.tiny:
        yolo = YoloV3Tiny()
    else:
        yolo = YoloV3()

    yolo.load_weights(FLAGS.weights)
    logging.info('weights loaded')

    tf.saved_model.save(yolo, FLAGS.output, signatures=trace_model_call(yolo))
    logging.info("model saved to: {}".format(FLAGS.output))

    model = tf.saved_model.load(FLAGS.output)
    infer = model.signatures[tf.saved_model.DEFAULT_SERVING_SIGNATURE_DEF_KEY]
    logging.info(infer.structured_outputs)

    class_names = [c.strip() for c in open(FLAGS.classes).readlines()]
    logging.info('classes loaded')

    img = tf.image.decode_image(open(FLAGS.image, 'rb').read(), channels=3)
    img = tf.expand_dims(img, 0)
    img = transform_images(img, 416)

    t1 = time.time()
    outputs = infer(img)
    boxes, scores, classes, nums = outputs["yolo_nms_0"], outputs[
        "yolo_nms_1_1"], outputs["yolo_nms_2_2"], outputs["yolo_nms_3_3"]

    pprint('=========================================')
    pprint(outputs)
    pprint('=========================================')
    t2 = time.time()
    logging.info('time: {}'.format(t2 - t1))

    logging.info('detections:')
    for i in range(nums[0]):
        logging.info('\t{}, {}, {}'.format(class_names[int(classes[0][i])],
                                           scores[0][i].numpy(),
                                           boxes[0][i].numpy()))


if __name__ == '__main__':
    try:
        app.run(main)
    except SystemExit:
        pass
