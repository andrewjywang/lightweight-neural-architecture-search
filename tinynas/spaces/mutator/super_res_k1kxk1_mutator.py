# Copyright (c) Alibaba, Inc. and its affiliates.
# The implementation is also open-sourced by the authors, and available at
# https://github.com/alibaba/lightweight-neural-architecture-search.

import bisect
import copy
import os
import random
import sys

from ..space_utils import smart_round
from .builder import * 

@MUTATORS.register_module(module_name = 'SuperResK1KXK1')
class SuperResK1KXK1Mutator():
    def __init__(self, 
                mutate_method_list,
                search_channel_list, 
                search_kernel_size_list, 
                search_layer_list,
                the_maximum_channel,
                btn_minimum_ratio,
                budget_layers,
                *args,
                **kwargs):
        self.btn_minimum_ratio = btn_minimum_ratio
        self.budget_layers = budget_layers

        minor_mutation_list = ['out', 'btn']
        kwargs.update(dict(candidates = minor_mutation_list))
        self.minor_method_mutator = build_mutator(default_args = kwargs)

        kwargs.update(dict(candidates = mutate_method_list))
        self.method_mutator = build_mutator(default_args = kwargs)

        kwargs.update(dict(candidates = search_channel_list), the_maximum_channel= the_maximum_channel)
        self.channel_mutator = build_channel_mutator(kwargs) 

        kwargs = dict(candidates = search_kernel_size_list ) 
        self.kernel_mutator = build_kernel_mutator(kwargs) 

        kwargs = dict(candidates = search_layer_list) 
        self.layer_mutator = build_layer_mutator(kwargs) 

    def __call__(self, block_id, structure_info_list, minor_mutation = False, *args, **kwargs):
        structure_info = structure_info_list[block_id]
        if block_id < len(structure_info_list) - 1:
            structure_info_next = structure_info_list[block_id + 1]
        structure_info = copy.deepcopy(structure_info)

        # coarse2fine mutation flag, only mutate the channels' output
        random_mutate_method = self.minor_method_mutator() if minor_mutation else self.method_mutator() 

        if random_mutate_method == 'out':
            new_out = self.channel_mutator(structure_info['out'])
            # Add the constraint: output_channel <= 4*input_channel
            new_out = min(4 * structure_info['in'], new_out)
            # add the constraint: next block, input_channel>output_channel/4.
            if block_id < len(
                    structure_info_list) - 1 and new_out < smart_round(
                        structure_info_next['out'] / 4):
                structure_info['out'] = smart_round(structure_info_next['out']
                                                    / 4)
            else:
                structure_info['out'] = new_out

        if random_mutate_method == 'k':
            new_k = self.kernel_mutator(structure_info['k'])
            structure_info['k'] = new_k

        if random_mutate_method == 'btn':
            new_btn = self.channel_mutator(structure_info['btn'])
            # Add the constraint: bottleneck_channel <= output_channel
            new_btn = min(structure_info['out'], new_btn)
            structure_info['btn'] = new_btn

        if random_mutate_method == 'L':
            new_L = self.layer_mutator(structure_info['L'])
            # add the constraint: the block 1 can't have the large layers.
            if block_id == 1:
                new_L = min(3, new_L)
            elif self.budget_layers:
                new_L = min(
                    int(self.budget_layers // 3 // (len(structure_info_list) - 2)),
                    new_L)

            structure_info['L'] = new_L

        # add the constraint: the btn must be larger than out/btn_minimum_ratio.
        if structure_info['btn'] < (structure_info['out'] / self.btn_minimum_ratio):
            structure_info['btn'] = smart_round(structure_info['out']
                                                / self.btn_minimum_ratio)

        return structure_info
