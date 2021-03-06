# coding=utf-8
# Copyright 2019 The TensorFlow Datasets Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""SUN (Scene UNderstanding) datasets."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import io
import os
import numpy as np

import tensorflow_datasets.public_api as tfds


_SUN397_CITATION = """\
@INPROCEEDINGS{Xiao:2010,
author={J. {Xiao} and J. {Hays} and K. A. {Ehinger} and A. {Oliva} and A. {Torralba}},
booktitle={2010 IEEE Computer Society Conference on Computer Vision and Pattern Recognition},
title={SUN database: Large-scale scene recognition from abbey to zoo},
year={2010},
volume={},
number={},
pages={3485-3492},
keywords={computer vision;human factors;image classification;object recognition;visual databases;SUN database;large-scale scene recognition;abbey;zoo;scene categorization;computer vision;scene understanding research;scene category;object categorization;scene understanding database;state-of-the-art algorithms;human scene classification performance;finer-grained scene representation;Sun;Large-scale systems;Layout;Humans;Image databases;Computer vision;Anthropometry;Bridges;Legged locomotion;Spatial databases}, 
doi={10.1109/CVPR.2010.5539970},
ISSN={1063-6919},
month={June},}
"""
_SUN397_DESCRIPTION = """\
The database contains 108,754 images of 397 categories, used in the
Scene UNderstanding (SUN) benchmark. The number of images varies across
categories, but there are at least 100 images per category.

The official release of the dataset defines 10 overlapping partitions of the
dataset, with 50 testing and training images in each.
Since TFDS requires the splits not to overlap, we provide a single split for
the entire dataset (named "full"). All images are converted to RGB.
"""
_SUN397_URL = "https://vision.princeton.edu/projects/2010/SUN/"


def _decode_image(fobj):
  """Reads and decodes an image from a file object as a Numpy array.

  The SUN dataset contains images in several formats (despite the fact that
  all of them have .jpg extension). Some of them are:
    - BMP (RGB)
    - PNG (grayscale, RGBA, RGB interlaced)
    - JPEG (RGB)
    - GIF (1-frame RGB)
  Since TFDS assumes that all images have the same number of channels, we
  convert all of them to RGB.

  Args:
    fobj: File object to read from.

  Returns:
    Numpy array with shape (height, width, channels).
  """

  buf = fobj.read()
  image = tfds.core.lazy_imports.cv2.imdecode(
      np.fromstring(buf, dtype=np.uint8), flags=3)  # Note: Converts to RGB.
  if image is None:
    # OpenCV misses support for some image formats contained in the dataset.
    image = tfds.core.lazy_imports.PIL_Image.open(io.BytesIO(buf))
    image = image.convert("RGB")
    image = np.array(image)

  # The GIF images contain a single frame.
  if len(image.shape) == 4:  # rank=4 -> rank=3
    image = image.reshape(image.shape[1:])

  return image


def _encode_image(image, image_format=None, fobj=None):
  """Encodes and writes an image in a Numpy array to a file object.

  Args:
    image: A numpy array with shape (height, width, channels).
    image_format: Encode and write the image in this format.
      If None, JPEG is used.
    fobj: File object to write the encoded image. Random access (seek) is
      required. If None, it creates a BytesIO file.

  Returns:
    Resulting file object. If fobj was given, the functions returns it.
  """
  if len(image.shape) != 3:
    raise ValueError("The image should have shape (height, width, channels)")

  # By default, for images with alpha channel use PNG, otherwise use JPEG.
  if image_format is None:
    image_format = "JPEG"

  # Remove extra channel for grayscale images, or PIL complains.
  if image.shape[-1] == 1:
    image = image.reshape(image.shape[:-1])

  fobj = fobj or io.BytesIO()
  image = tfds.core.lazy_imports.PIL_Image.fromarray(image)
  image.save(fobj, format=image_format)
  fobj.seek(0)
  return fobj


def _process_image_file(fobj):
  """Process image files from the dataset."""
  # We need to read the image files and convert them to JPEG, since some files
  # actually contain GIF, PNG or BMP data (despite having a .jpg extension) and
  # some encoding options that will make TF crash in general.
  image = _decode_image(fobj)
  return _encode_image(image, image_format="JPEG")


class Sun397(tfds.core.GeneratorBasedBuilder):
  """Sun397 Scene Recognition Benchmark."""

  VERSION = tfds.core.Version("1.0.0")

  def _info(self):
    names_file = tfds.core.get_tfds_path(
        os.path.join("image", "sun397_labels.txt"))
    return tfds.core.DatasetInfo(
        builder=self,
        description=_SUN397_DESCRIPTION,
        features=tfds.features.FeaturesDict({
            "file_name": tfds.features.Text(),
            "image": tfds.features.Image(shape=(None, None, 3)),
            "label": tfds.features.ClassLabel(names_file=names_file),
        }),
        urls=[_SUN397_URL],
        citation=_SUN397_CITATION)

  def _split_generators(self, dl_manager):
    tar_gz_path = dl_manager.download(_SUN397_URL + "SUN397.tar.gz")
    if os.path.isdir(tar_gz_path):
      # While testing: download() returns the dir containing the tests files.
      tar_gz_path = os.path.join(tar_gz_path, "SUN397.tar.gz")

    resource = tfds.download.Resource(
        path=tar_gz_path,
        extract_method=tfds.download.ExtractMethod.TAR_GZ_STREAM)
    return [
        tfds.core.SplitGenerator(
            name=tfds.Split("full"),
            num_shards=20,  # size(shard) ~= 2GB.
            gen_kwargs=dict(archive=dl_manager.iter_archive(resource)))
    ]

  def _generate_examples(self, archive):
    prefix_len = len("SUN397")
    for filepath, fobj in archive:
      if filepath.endswith(".jpg"):
        # Note: all files in the tar.gz are in SUN397/...
        filename = filepath[prefix_len:]
        # Example:
        # From filename: /c/car_interior/backseat/sun_aenygxwhhmjtisnf.jpg
        # To class: /c/car_interior/backseat
        label = "/".join(filename.split("/")[:-1])
        image = _process_image_file(fobj)
        yield {
            "file_name": filename,
            "image": image,
            "label": label,
        }
