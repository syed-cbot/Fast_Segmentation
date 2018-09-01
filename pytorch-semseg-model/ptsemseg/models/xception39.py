"""
Ported to pytorch thanks to [tstandley](https://github.com/tstandley/Xception-PyTorch)
@author: tstandley
Adapted by cadene
Creates an Xception Model as defined in:
Francois Chollet
Xception: Deep Learning with Depthwise Separable Convolutions
https://arxiv.org/pdf/1610.02357.pdf
This weights ported from the Keras implementation. Achieves the following performance on the validation set:
Loss:0.9173 Prec@1:78.892 Prec@5:94.292
REMEMBER to set your image size to 3x299x299 for both test and validation
normalize = transforms.Normalize(mean=[0.5, 0.5, 0.5],
                                  std=[0.5, 0.5, 0.5])
The resize parameter of the validation transform should be 333, and make sure to center crop at 299x299
"""
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.utils.model_zoo as model_zoo
from torch.nn import init

__all__ = ['xception']

pretrained_settings = {
	'xception': {
		'imagenet': {
			'url': 'http://data.lip6.fr/cadene/pretrainedmodels/xception-b5690688.pth',
			'input_space': 'RGB',
			'input_size': [3, 299, 299],
			'input_range': [0, 1],
			'mean': [0.5, 0.5, 0.5],
			'std': [0.5, 0.5, 0.5],
			'num_classes': 1000,
			'scale': 0.8975
		# The resize parameter of the validation transform should be 333, and make sure to center crop at 299x299
		}
	}
}


class SeparableConv2d(nn.Module):
	def __init__(self, in_channels, out_channels, kernel_size=1, stride=1, padding=0, dilation=1, bias=False):
		super(SeparableConv2d, self).__init__()

		self.conv1 = nn.Conv2d(in_channels, in_channels, kernel_size, stride, padding, dilation, groups=in_channels, bias=bias)
		self.pointwise = nn.Conv2d(in_channels, out_channels, 1, 1, 0, 1, 1, bias=bias)

	def forward(self, x):
		x = self.conv1(x)
		x = self.pointwise(x)
		return x


class Block(nn.Module):
	def __init__(self, in_filters, out_filters, reps, strides=1, start_with_relu=True, grow_first=True):
		super(Block, self).__init__()

		if out_filters != in_filters or strides != 1:
			self.skip = nn.Conv2d(in_filters, out_filters, 1, stride=strides, bias=False)
			self.skipbn = nn.BatchNorm2d(out_filters)
		else:
			self.skip = None

		self.relu = nn.ReLU(inplace=True)
		rep = []

		filters = in_filters
		if grow_first:
			rep.append(self.relu)
			rep.append(SeparableConv2d(in_filters, out_filters, 3, stride=1, padding=1, bias=False))
			rep.append(nn.BatchNorm2d(out_filters))
			filters = out_filters

		for i in range(reps - 1):
			rep.append(self.relu)
			rep.append(SeparableConv2d(filters, filters, 3, stride=1, padding=1, bias=False))
			rep.append(nn.BatchNorm2d(filters))

		if not grow_first:
			rep.append(self.relu)
			rep.append(SeparableConv2d(in_filters, out_filters, 3, stride=1, padding=1, bias=False))
			rep.append(nn.BatchNorm2d(out_filters))

		if not start_with_relu:
			rep = rep[1:]
		else:
			rep[0] = nn.ReLU(inplace=False)

		if strides != 1:
			rep.append(nn.MaxPool2d(3, strides, 1))
		self.rep = nn.Sequential(*rep)

	def forward(self, inp):
		x = self.rep(inp)

		if self.skip is not None:
			skip = self.skip(inp)
			skip = self.skipbn(skip)
		else:
			skip = inp

		x += skip
		return x

# class GlobalAveragePooling(nn.Module):
# 	# aap is adaptive_avg_pool2d
# 	def __init__(self, input_aap, outputsize_aap, num_classes):
# 		super(GlobalAveragePooling, self).__init__()
# 		self.aap = F.adaptive_avg_pool2d(input=input_aap, output_size=outputsize_aap)
# 		self.fc_aap = nn.Linear(in_features=2048, out_features=num_classes)
#
# 	def forward(self, x):
# 		x = self.relu(x)
# 		x = self.aap(x)
# 		x = x.view(x.size(0), -1)
# 		x = self.fc_aap(x)
# 		return x

class Xception(nn.Module):
	"""
	Xception optimized for the ImageNet dataset, as specified in
	https://arxiv.org/pdf/1610.02357.pdf
	"""

	def __init__(self, num_classes=1000):
		""" Constructor
		Args:
			num_classes: number of classes
		"""
		super(Xception, self).__init__()
		self.num_classes = num_classes

		self.conv1_xception39 = nn.Conv2d(in_channels=3, out_channels=8, kernel_size=3, stride=2, padding=0, bias=False)
		self.maxpool_xception39 = nn.MaxPool2d(kernel_size=3, stride=2)

		# P3
		self.block1_xception39 = Block(in_filters=8, out_filters=16, reps=1, strides=2, start_with_relu=True, grow_first=True)
		self.block2_xception39 = Block(in_filters=16, out_filters=16, reps=3, strides=1, start_with_relu=True, grow_first=True)

		# P4
		self.block3_xception39 = Block(in_filters=16, out_filters=32, reps=1, strides=2, start_with_relu=True, grow_first=True)
		self.block4_xception39 = Block(in_filters=32, out_filters=32, reps=7, strides=1, start_with_relu=True, grow_first=True)

		# P5
		self.block5_xception39 = Block(in_filters=32, out_filters=64, reps=1, strides=2, start_with_relu=True, grow_first=True)
		self.block6_xception39 = Block(in_filters=64, out_filters=64, reps=3, strides=1, start_with_relu=True, grow_first=True)

		self.fc_xception39 = nn.Linear(2048, num_classes)


		self.conv1 = nn.Conv2d(3, 32, 3, 2, 0, bias=False)
		self.bn1 = nn.BatchNorm2d(32)
		self.relu = nn.ReLU(inplace=True)

		self.conv2 = nn.Conv2d(32, 64, 3, bias=False)
		self.bn2 = nn.BatchNorm2d(64)
		# do relu here

		self.block1 = Block(64, 128, 2, 2, start_with_relu=False, grow_first=True)
		self.block2 = Block(128, 256, 2, 2, start_with_relu=True, grow_first=True)
		self.block3 = Block(256, 728, 2, 2, start_with_relu=True, grow_first=True)

		self.block4 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
		self.block5 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
		self.block6 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
		self.block7 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)

		self.block8 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
		self.block9 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
		self.block10 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)
		self.block11 = Block(728, 728, 3, 1, start_with_relu=True, grow_first=True)

		self.block12 = Block(728, 1024, 2, 2, start_with_relu=True, grow_first=False)

		self.conv3 = SeparableConv2d(1024, 1536, 3, 1, 1)
		self.bn3 = nn.BatchNorm2d(1536)

		# do relu here
		self.conv4 = SeparableConv2d(1536, 2048, 3, 1, 1)
		self.bn4 = nn.BatchNorm2d(2048)

		self.fc = nn.Linear(2048, num_classes)

	# #------- init weights --------
	# for m in self.modules():
	#     if isinstance(m, nn.Conv2d):
	#         n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
	#         m.weight.data.normal_(0, math.sqrt(2. / n))
	#     elif isinstance(m, nn.BatchNorm2d):
	#         m.weight.data.fill_(1)
	#         m.bias.data.zero_()
	# #-----------------------------

	def features(self, input):

		y = self.conv1_xception39(input)
		print('the size of xception39 after conv1', y.size())
		y = self.maxpool_xception39(y)
		print('the size of xception39 after maxpool', y.size())

		y = self.block1_xception39(y)
		print('the size of xception39 after block1', y.size())
		y = self.block2_xception39(y)
		print('the size of xception39 after block2', y.size())
		y = self.block3_xception39(y)
		print('the size of xception39 after block3', y.size())
		y = self.block4_xception39(y)
		print('the size of xception39 after block4', y.size())
		y = self.block5_xception39(y)
		print('the size of xception39 after block5', y.size())
		y = self.block6_xception39(y)
		print('the size of xception39 after block6', y.size())
		# y = self.avg(y)
		# print('the size of xception39 after ', y.size())
		y = F.adaptive_avg_pool2d(y, (1, 1))
		y = y.view(y.size(0), -1)
		print('the size of xception39 is ', y.size())
		# y = self.fc_xception39(2048, 1000)

		x = self.conv1(input)
		x = self.bn1(x)
		x = self.relu(x)
		print('x after conv1: ', x.size())

		x = self.conv2(x)
		x = self.bn2(x)
		x = self.relu(x)
		print('x after conv2: ', x.size())

		x = self.block1(x)
		x = self.block2(x)
		x = self.block3(x)
		print('x after block 3: ', x.size())

		x = self.block4(x)
		x = self.block5(x)
		x = self.block6(x)
		x = self.block7(x)

		x = self.block8(x)
		x = self.block9(x)
		x = self.block10(x)
		x = self.block11(x)
		print('x after block 11: ', x.size())
		x = self.block12(x)

		x = self.conv3(x)
		x = self.bn3(x)
		x = self.relu(x)

		x = self.conv4(x)
		x = self.bn4(x)
		print('x after conv4: ', x.size())
		return x

	def logits(self, features):

		x = self.relu(features)
		print('in logits function，the size of xception after relu', x.size())
		x = F.adaptive_avg_pool2d(x, (1, 1))
		print('in logits function，the size of xception after adaptive_avg_pool2d', x.size())
		x = x.view(x.size(0), -1)
		print('in logits function，the size of xception after view', x.size())
		x = self.last_linear(x)
		print('in logits function，the size of xception after last_linear', x.size())
		return x

	def forward(self, input):
		x = self.features(input)
		print('the size of xception after features is ', x.size())
		x = self.logits(x)
		print('the size of xception after logits is ', x.size())
		return x


def xception39(num_classes=1000, pretrained='imagenet'):
	import torch
	model = Xception(num_classes=num_classes)
	if pretrained:
		settings = pretrained_settings['xception'][pretrained]
		assert num_classes == settings['num_classes'], \
			"num_classes should be {}, but is {}".format(settings['num_classes'], num_classes)

		model = Xception(num_classes=num_classes)
		# model.load_state_dict(model_zoo.load_url(settings['url']))
		model.load_state_dict(torch.load('/home/donghao/.torch/models/xception-squeezzed.pth'))
		print('the model has been loaded successfully')
		model.input_space = settings['input_space']
		model.input_size = settings['input_size']
		model.input_range = settings['input_range']
		model.mean = settings['mean']
		model.std = settings['std']

	# TODO: ugly
	model.last_linear = model.fc
	del model.fc
	return model