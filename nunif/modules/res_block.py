import torch
import torch.nn as nn
from .pad import Pad
from .norm import FRN2d, TLU2d
from .attention import SEBlock


class ResBlock(nn.Module):
    def __init__(
            self,
            in_channels, out_channels,
            stride=1,
            bias=False,
            padding_mode="zeros",
            activation_layer=None,
            norm_layer=None,
            attention_layer=None,
            valid_stride=False):
        super().__init__()
        assert stride in {1, 2}

        if activation_layer is None:
            activation_layer = lambda dim: nn.ReLU(inplace=True)
        if norm_layer is None:
            norm_layer = lambda dim: nn.BatchNorm2d(dim)
        if attention_layer is None:
            attention_layer = lambda dim: nn.Identity()
        if valid_stride and stride == 2:
            first_kernel_size = 4
            shortcut_kernel_size = 2
        else:
            first_kernel_size = 3
            shortcut_kernel_size = 1
        if padding_mode == "none":
            padding = 0
            padding_mode = "zeros"
        else:
            padding = 1

        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=first_kernel_size,
                      stride=stride, padding=padding, padding_mode=padding_mode, bias=bias),
            norm_layer(out_channels),
            activation_layer(out_channels),
            nn.Conv2d(out_channels, out_channels, kernel_size=3,
                      stride=1, padding=padding, padding_mode=padding_mode, bias=bias),
            norm_layer(out_channels))
        if stride == 2 or in_channels != out_channels:
            self.identity = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=shortcut_kernel_size,
                          stride=stride, padding=0, bias=bias),
                norm_layer(out_channels))
        else:
            self.identity = nn.Identity()
        self.attn = attention_layer(out_channels)
        self.act = activation_layer(out_channels)

    def forward(self, x):
        return self.attn(self.act(self.conv(x) + self.identity(x)))


def ResBlockBNReLU(in_channels, out_channels, stride=1, bias=False,
                   padding_mode="zeros", valid_stride=False):
    return ResBlock(in_channels, out_channels, stride, bias,
                    padding_mode=padding_mode, valid_stride=valid_stride)


def ResBlockLReLU(in_channels, out_channels, stride=1, bias=True,
                  padding_mode="zeros", valid_stride=True):
    return ResBlock(
        in_channels, out_channels, stride, bias,
        padding_mode=padding_mode,
        norm_layer=lambda dim: nn.Identity(),
        activation_layer=lambda dim: nn.LeakyReLU(0.2, inplace=True),
        valid_stride=valid_stride)


def ResBlockSELReLU(in_channels, out_channels, stride=1, bias=True,
                    padding_mode="zeros", se=True, valid_stride=True):
    if se:
        attention_layer = lambda dim: SEBlock(dim, bias=True)
    else:
        attention_layer = lambda dim: nn.Identity()

    return ResBlock(
        in_channels, out_channels, stride, bias,
        padding_mode=padding_mode,
        norm_layer=lambda dim: nn.Identity(),
        activation_layer=lambda dim: nn.LeakyReLU(0.2, inplace=True),
        attention_layer=attention_layer,
        valid_stride=valid_stride)


def ResBlockBNLReLU(in_channels, out_channels, stride=1, bias=False,
                    padding_mode="zeros", valid_stride=False):
    return ResBlock(
        in_channels, out_channels, stride, bias,
        padding_mode=padding_mode,
        norm_layer=lambda dim: nn.BatchNorm2d(dim),
        activation_layer=lambda dim: nn.LeakyReLU(0.2, inplace=True),
        valid_stride=valid_stride)


def ResBlockFRN(in_channels, out_channels, stride=1, bias=False,
                padding_mode="zeros", valid_stride=False):
    return ResBlock(
        in_channels, out_channels, stride, bias,
        padding_mode=padding_mode,
        norm_layer=lambda dim: FRN2d(dim),
        activation_layer=lambda dim: TLU2d(dim),
        valid_stride=valid_stride)


class ResGroup(nn.Module):
    def __init__(self, in_channels, out_channels, num_layers, stride=1, layer=None, **layer_kwargs):
        super().__init__()
        assert (stride in {1, 2})
        if layer is None:
            layer = ResBlock
        layers = []
        for i in range(num_layers):
            if i == 0:
                layers.append(layer(in_channels, out_channels, stride, **layer_kwargs))
            else:
                layers.append(layer(out_channels, out_channels, 1, **layer_kwargs))
        self.layers = nn.Sequential(*layers)

    def forward(self, x):
        return self.layers(x)


def _spec():
    device = "cuda:0"
    resnet = nn.Sequential(
        nn.Conv2d(1, 64, 3, 1, 1),
        nn.BatchNorm2d(64),
        nn.ReLU(inplace=True),
        ResGroup(64, 64, num_layers=3, stride=2),
        ResGroup(64, 128, num_layers=3, stride=2),
        ResGroup(128, 256, num_layers=3, stride=2),
        ResGroup(256, 512, num_layers=3, stride=2),
    ).to(device)
    x = torch.rand((8, 1, 256, 256)).to(device)
    z = resnet(x)
    print(resnet)
    print(z.shape)

    resnet = nn.Sequential(
        nn.Conv2d(1, 64, 3, 1, 1),
        nn.BatchNorm2d(64),
        nn.ReLU(inplace=True),
        ResGroup(64, 64, num_layers=3, stride=2, layer=ResBlockLReLU),
        ResGroup(64, 128, num_layers=3, stride=2, layer=ResBlockBNLReLU),
        ResGroup(128, 256, num_layers=3, stride=2, layer=ResBlockSELReLU),
        ResGroup(256, 512, num_layers=3, stride=2, layer=ResBlockFRN),
    ).to(device)
    x = torch.rand((8, 1, 256, 256)).to(device)
    z = resnet(x)
    print(resnet)
    print(z.shape)


if __name__ == "__main__":
    _spec()
