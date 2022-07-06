#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: © 2022 California Institute of Technology.
# SPDX-FileCopyrightText: © 2022 Lee McCuller <mcculler@caltech.edu>
# NOTICE: authors should document their contributions in concisely in NOTICE
# with details inline in source files, comments, and docstrings.
"""
Functions to create a SISO state space system from inputs.
"""
import numbers
import numpy as np

from . import mimo
from .. import SISO


class MIMOFResponse(mimo.MIMO):
    """
    Class to hold transfer function response of MIMO systems
    """

    def __init__(
        self, *,
        f=None,
        w=None,
        s=None,
        tf=None,
        snr=None,
        inputs=None,
        outputs=None,
        hermitian: bool = True,
        time_symm: bool = False,
    ):
        """
        snr of None means that the tf was computed numerically. A snr of False (or 0) means that it is from data but is unknown

        tf should be a matrix
        """
        domain = None
        if f is not None:
            domain = f
            # must use the dict assignment since there are properties which alias
            self.__dict__['f'] = f
        if w is not None:
            assert(domain is None)
            domain = w
            self.__dict__['w'] = w
        if s is not None:
            assert(domain is None)
            domain = s
            self.__dict__['s'] = s
        assert(domain is not None)
        shape = domain.shape

        self.tf_sm = tf
        self.tf = np.broadcast_to(self.tf_sm, shape + self.tf_sm.shape[-2:])

        self.snr_sm = np.asarray(snr)
        self.snr = np.broadcast_to(self.snr_sm, self.tf.shape)

        self.hermitian = hermitian
        self.time_symm = time_symm

        self.inputs = inputs
        self.outputs = outputs
        return

    @property
    def f(self):
        w = self.__dict__.get('w', None)
        if w is not None:
            f = w / (2 * np.pi)
        else:
            s = self.__dict__.get('s', None)
            if s is not None:
                f = s / (2j * np.pi)
        self.__dict__['f'] = f
        return f

    @property
    def w(self):
        f = self.__dict__.get('f', None)
        if f is not None:
            w = f * (2 * np.pi)
        else:
            s = self.__dict__.get('s', None)
            if s is not None:
                w = s / 1j
        self.__dict__['w'] = w
        return w

    @property
    def s(self):
        f = self.__dict__.get('f', None)
        if f is not None:
            s = f * (2j * np.pi)
        else:
            w = self.__dict__.get('w', None)
            if w is not None:
                s = w * 1j
        self.__dict__['s'] = s
        return s

    def siso(self, row, col):
        """
        convert a single output (row) and input (col) into a SISO
        representation
        """
        r = self.outputs[row]
        c = self.inputs[col]
        return SISO.SISOResponse(
            tf=self.tf_sm[..., r, c],
            **self.__init_kw()
        )

    def __getitem__(self, key):
        row, col = key

        def apply_map(group, length):
            if isinstance(row, slice):
                # make the klst just be using the slice
                klst = range(length)[row]
            elif isinstance(row, (list, tuple, set)):
                klst = []
                for k in row:
                    if isinstance(row, str):
                        k_i = self.outputs[k]
                    else:
                        k_i = k
                    klst.append(k_i)
            else:
                # will be a single index
                if isinstance(row, str):
                    klst = [self.outputs[k]]
                else:
                    klst = [k]
            return klst

        r = apply_map(row, self.C.shape[-2])
        c = apply_map(col, self.B.shape[-1])

        def map_into(rev, lst):
            d = {}
            for idx, k in enumerate(lst):
                kset = rev[lst]
                for v in kset:
                    d[v] = idx
            return d

        inputs = map_into(rev=self.inputs_rev, lst=c)
        outputs = map_into(rev=self.outputs_rev, lst=r)

        return self.__class__(
            tf=self.tf[..., r, c],
            inputs=inputs,
            outputs=outputs,
            **self.__init_kw()
        )

    def rename(self, renames, which='both'):
        """
        Rename inputs and outputs of the statespace

        which: can be inputs, outputs, or both (the default).

        """
        raise NotImplementedError("TODO")
        return

    def __init_kw(self, other=None, snr=None):
        """
        Build a kw dictionary for building a new version of this class
        """
        if other is None:
            if snr is None:
                snr = self.snr_sm
            kw = dict(
                snr=snr,
                hermitian=self.hermitian,
                time_symm=self.time_symm,
            )
        else:
            if snr is None:
                if self.snr_sm is None:
                    snr = other.snr_sm
                elif other.snr_sm is None:
                    snr = self.snr_sm
                else:
                    snr = (self.snr_sm**-2 + other.snr_sm**-2)**-0.5
            kw = dict(
                snr=snr,
                hermitian=self.hermitian and other.hermitian,
                time_symm=self.time_symm and other.time_symm,
            )
        f = self.__dict__.get('f', None)
        if f is not None:
            kw['f'] = f
        else:
            w = self.__dict__.get('w', None)
            if w is not None:
                kw['w'] = w
            else:
                kw['s'] = self.__dict__['s']
        return kw

    def check_domain(self, other):
        f = self.__dict__.get('f', None)
        if f is not None:
            if f is other.f:
                return
            np.testing.assert_allclose(f, other.f)
        else:
            w = self.__dict__.get('w', None)
            if w is not None:
                if w is other.w:
                    return
                np.testing.assert_allclose(w, other.w)
            else:
                if self.s is other.s:
                    return
                np.testing.assert_allclose(self.s, other.s)

    def __mul__(self, other):
        """
        """
        if isinstance(other, numbers.Number):
            self.__class__(
                tf=self.tf_sm * other,
                inputs=self.inputs,
                outputs=self.outputs,
                **self.__init_kw()
            )
        return NotImplemented

    def __rmul__(self, other):
        """
        """
        if isinstance(other, numbers.Number):
            self.__class__(
                tf=other * self.tf_sm,
                inputs=self.inputs,
                outputs=self.outputs,
                **self.__init_kw()
            )
        else:
            return NotImplemented
        return NotImplemented

    def __truediv__(self, other):
        """
        """
        if isinstance(other, numbers.Number):
            self.__class__(
                tf=self.tf_sm / other,
                inputs=self.inputs,
                outputs=self.outputs,
                **self.__init_kw()
            )
        else:
            return NotImplemented

    def __rtruediv__(self, other):
        """
        """
        return NotImplemented

    def __pow__(self, other):
        """
        """
        return NotImplemented

    def __add__(self, other):
        """
        """
        if isinstance(other, MIMOResponse):
            self.check_domain(other)
            self.__class__(
                tf=self.tf_sm + other.tf_sm,
                inputs=self.inputs,
                outputs=self.outputs,
                **self.__init_kw(other)
            )
        elif isinstance(other, numbers.Number):
            tf = self.tf_sm + other
            if self.snr_sm:
                snr = (self.snr_sm * abs(self.tf_sm)) / abs(tf)
            else:
                snr = self.snr_sm
            self.__class__(
                tf=tf,
                inputs=self.inputs,
                outputs=self.outputs,
                **self.__init_kw(snr=snr)
            )
        return NotImplemented

    def __radd__(self, other):
        """
        """
        if isinstance(other, numbers.Number):
            tf = other + self.tf_sm
            if self.snr_sm:
                snr = (self.snr_sm * abs(self.tf_sm)) / abs(tf)
            else:
                snr = self.snr_sm
            self.__class__(
                tf=tf,
                **self.__init_kw(snr=snr)
            )
        else:
            return NotImplemented
        return NotImplemented

    def __sub__(self, other):
        """
        """
        if isinstance(other, numbers.Number):
            tf = self.tf_sm - other
            if self.snr_sm:
                snr = (self.snr_sm * abs(self.tf_sm)) / abs(tf)
            else:
                snr = self.snr_sm
            self.__class__(
                tf=tf,
                inputs=self.inputs,
                outputs=self.outputs,
                **self.__init_kw(snr=snr)
            )
        return NotImplemented

    def __rsub__(self, other):
        """
        """
        if isinstance(other, numbers.Number):
            tf = other - self.tf_sm
            if self.snr_sm:
                snr = (self.snr_sm * abs(self.tf_sm)) / abs(tf)
            else:
                snr = self.snr_sm
            self.__class__(
                tf=tf,
                inputs=self.inputs,
                outputs=self.outputs,
                **self.__init_kw(snr=snr)
            )
        else:
            return NotImplemented
        return NotImplemented
