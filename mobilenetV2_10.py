import math
import numpy as np
import tensorflow as tf
from tensorflow.keras import backend
from keras import backend as K
from keras.preprocessing import image
from keras.models import Model
from keras.layers.normalization import BatchNormalization
from keras.layers import Conv2D, Add, ZeroPadding2D, GlobalAveragePooling2D, Dropout, Dense, Lambda, Multiply, LeakyReLU
from keras.layers import MaxPooling2D, Activation, DepthwiseConv2D, Input, GlobalMaxPooling2D
def relu6(x):
    return K.relu(x, max_value=6)
def correct_pad(inputs, kernel_size):
    img_dim = 1
    input_size = backend.int_shape(inputs)[img_dim:(img_dim + 2)]

    if isinstance(kernel_size, int):
        kernel_size = (kernel_size, kernel_size)

    if input_size[0] is None:
        adjust = (1, 1)
    else:
        adjust = (1 - input_size[0] % 2, 1 - input_size[1] % 2)

    correct = (kernel_size[0] // 2, kernel_size[1] // 2)

    return ((correct[0] - adjust[0], correct[0]),
            (correct[1] - adjust[1], correct[1]))

def _make_divisible(v, divisor, min_value=None):
    if min_value is None:
        min_value = divisor
    new_v = max(min_value, int(v + divisor / 2) // divisor * divisor)
    if new_v < 0.9 * v:
        new_v += divisor
    return new_v

def MobileNetV2(input_shape, classes, expansion=6, alpha=1):
    expansion = expansion
    rows = input_shape[0]
    img_input = Input(shape=input_shape)
    # 224,224,3 -> 112,112,32
    first_block_filters = _make_divisible(32 * alpha, 8)
    x = ZeroPadding2D(padding=correct_pad(img_input, 3),
                      name='Conv1_pad')(img_input)
    x = Conv2D(first_block_filters,
               kernel_size=3,
               strides=(2, 2),
               padding='valid',
               use_bias=False,
               name='Conv1')(x)
    x = BatchNormalization(epsilon=1e-3,
                           momentum=0.999)(x)
    x = Activation(relu6)(x)

    # 112,112,32 -> 112,112,16
    x = _inverted_res_block(x, filters=16, alpha=alpha, stride=1,
                            expansion=1, block_id=0)

    # 112,112,16 -> 56,56,24
    x = _inverted_res_block(x, filters=24, alpha=alpha, stride=2,
                            expansion=expansion, block_id=1)
    x = _inverted_res_block(x, filters=24, alpha=alpha, stride=1,
                            expansion=expansion, block_id=2)

    # 56,56,24 -> 28,28,32
    x = _inverted_res_block(x, filters=32, alpha=alpha, stride=2,
                            expansion=expansion, block_id=3)
    x = _inverted_res_block(x, filters=32, alpha=alpha, stride=1,
                            expansion=expansion, block_id=4)
    x = _inverted_res_block(x, filters=32, alpha=alpha, stride=1,
                            expansion=expansion, block_id=5)

    # 28,28,32 -> 14,14,64
    x = _inverted_res_block(x, filters=64, alpha=alpha, stride=2,
                            expansion=expansion, block_id=6)
    x = _inverted_res_block(x, filters=64, alpha=alpha, stride=1,
                            expansion=expansion, block_id=7)
    x = _inverted_res_block(x, filters=64, alpha=alpha, stride=1,
                            expansion=expansion, block_id=8)
    x = _inverted_res_block(x, filters=64, alpha=alpha, stride=1,
                            expansion=expansion, block_id=9)

    # 14,14,64 -> 14,14,96
    x = _inverted_res_block(x, filters=96, alpha=alpha, stride=1,
                            expansion=expansion, block_id=10)
    x = _inverted_res_block(x, filters=96, alpha=alpha, stride=1,
                            expansion=expansion, block_id=11)
    x = _inverted_res_block(x, filters=96, alpha=alpha, stride=1,
                            expansion=expansion, block_id=12)
    # 14,14,96 -> 7,7,160
    x = _inverted_res_block(x, filters=160, alpha=alpha, stride=2,
                            expansion=expansion, block_id=13)
    x = _inverted_res_block(x, filters=160, alpha=alpha, stride=1,
                            expansion=expansion, block_id=14)
    x = _inverted_res_block(x, filters=160, alpha=alpha, stride=1,
                            expansion=expansion, block_id=15)

    # 7,7,160 -> 7,7,320
    x = _inverted_res_block(x, filters=320, alpha=alpha, stride=1,
                            expansion=expansion, block_id=16)

    if alpha > 1.0:
        last_block_filters = _make_divisible(1280 * alpha, 8)
    else:
        last_block_filters = 1280

    # 7,7,320 -> 7,7,1280
    x = Conv2D(last_block_filters,
               kernel_size=1,
               use_bias=False,
               name='Conv_1')(x)
    x = BatchNormalization(epsilon=1e-3,
                           momentum=0.999)(x)
    x = Activation(relu6)(x)

    # 7,7,1280 -> 1,1,1280
    x = GlobalAveragePooling2D()(x)

    x = Dense(classes, activation='softmax', use_bias=True)(x)

    inputs = img_input

    model = Model(inputs, x, name='mobilenetv2_%0.2f_%s' % (alpha, rows))

    return model


def _inverted_res_block(inputs, expansion, stride, alpha, filters, block_id):
    in_channels = backend.int_shape(inputs)[-1]
    pointwise_conv_filters = int(filters * alpha)
    pointwise_filters = _make_divisible(pointwise_conv_filters, 8)
    x = inputs
    prefix = 'block_{}_'.format(block_id)

    x = Conv2D(expansion * in_channels,
               kernel_size=1,
               padding='same',
               use_bias=False,
               activation=None,
               name=prefix + 'expand')(x)
    x = BatchNormalization(epsilon=1e-3,
                           momentum=0.999,
                           name=prefix + 'expand_BN')(x)
    x = Activation(relu6, name=prefix + 'expand_relu')(x)

    if stride == 2:
        x = ZeroPadding2D(padding=correct_pad(x, 3),
                          name=prefix + 'pad')(x)

    # part2 可分离卷积
    x = DepthwiseConv2D(kernel_size=3,
                        strides=stride,
                        activation=None,
                        use_bias=False,
                        padding='same' if stride == 1 else 'valid',
                        name=prefix + 'depthwise')(x)
    x = BatchNormalization(epsilon=1e-3,
                           momentum=0.999,
                           name=prefix + 'depthwise_BN')(x)

    x = Activation(relu6, name=prefix + 'depthwise_relu')(x)

    # part3压缩特征，而且不使用relu函数，保证特征不被破坏
    x = Conv2D(pointwise_filters,
               kernel_size=1,
               padding='same',
               use_bias=False,
               activation=None,
               name=prefix + 'project')(x)

    x = BatchNormalization(epsilon=1e-3,
                           momentum=0.999,
                           name=prefix + 'project_BN')(x)

    if in_channels == pointwise_filters and stride == 1:
        return Add(name=prefix + 'add')([inputs, x])
    return x


