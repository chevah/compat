# Copyright (c) 2011 Adi Roiban.
# See LICENSE for details.
"""
Module for launching Windows services.
"""
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import

import os
import pywintypes
import servicemanager
import sys
import traceback
import win32service
import win32serviceutil

from chevah.compat.helpers import _


class ChevahNTService(win32serviceutil.ServiceFramework, object):
    """
    Basic NT service implementation.
    """
    __version__ = u'Define version here.'
    _svc_name_ = u'Define service name here.'
    _svc_display_name_ = u'Define service display name here.'
    _win32serviceutil = win32serviceutil
    _service_manager = servicemanager

    def __init__(self, *args):
        # This is the upstream __init__ code.
        # It is copied here to help with testing as the upstream code
        # is untestable since it imports servicemanager inside the method.
        service_name, = args[0]

        # FIXME:1328: isolate registry creating code
        self.ssh = self._service_manager.RegisterServiceCtrlHandler(
            service_name, self.ServiceCtrlHandlerEx, True)
        self._service_manager.SetEventSourceName(service_name)
        self.checkPoint = 0

        try:
            self.initialize()
        except Exception:
            self.error(
                u'Failed to initialize the service. '
                u'Consult the other information events for more details, '
                u'or start the service in debug mode. %s' % (
                    traceback.format_exc()))
            self.SvcStop()

    def error(self, message):
        """
        Log an Error event.
        """
        self._service_manager.LogErrorMsg(message)

    def info(self, message):
        """
        Log an Information event.
        """
        self._service_manager.LogInfoMsg(message)

    def SvcStop(self):
        """
        Main entry point for service stopping.
        """
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.stop()
        self.info(u'Service stopped.')

    def SvcDoRun(self):
        """
        Main entry point for service execution.
        """
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        try:
            # Start everything up
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
            self.info('Service started.')

            # After start this thread execution will be blocked.
            self.start()
        except Exception:
            # For right now just log the error.
            self.error(
                'Failed to start the service. For more information, start '
                'the service in debug mode. %s' % (traceback.format_exc()))

    def initialize(self):
        """
        Initialize the service.
        """
        raise NotImplementedError(
            'Use this method for initializing your service.')

    def start(self):
        """
        Starts the service.
        """
        raise NotImplementedError(
            'Use this method for starting your service.')

    def stop(self):
        """
        Stops the service.
        """
        raise NotImplementedError(
            'Use this method for stopping your service.')


def install_nt_service(service_class, options):
    '''Install an NT service.'''
    try:
        module_path = sys.modules[service_class.__module__].__file__
    except AttributeError:
        # maybe py2exe went by.
        from sys import executable
        module_path = executable
    module_file = os.path.splitext(os.path.abspath(module_path))[0]
    service_class._svc_reg_class_ = '%s.%s' % (
        module_file, service_class.__name__)

    try:
        win32serviceutil.InstallService(
            service_class._svc_reg_class_,
            service_class._svc_name_,
            service_class._svc_display_name_,
            startType=win32service.SERVICE_AUTO_START,
            )
        print(_(
            'Service "%s" successfully installed.\n'
            'Please use "sc" command or Windows Services to manage '
            'this service.' % (service_class._svc_name_)))
    except pywintypes.error as error:
        if error[0] == 5:
            print(_(
                'You do not have permissions to install this service.\n'
                'Please install the service as an administrator.'))
        else:
            print(_(
                'Failed to install the service %s:%s.\n'
                '%s:%d %s' % (
                    service_class._svc_name_,
                    service_class._svc_display_name_,
                    error[1], error[0], error[2])))
