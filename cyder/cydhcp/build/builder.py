from __future__ import unicode_literals

import os
import shlex
import subprocess
import sys
import syslog
from traceback import format_exception

from cyder.base.constants import IP_TYPE_4, IP_TYPE_6
from cyder.base.mixins import MutexMixin
from cyder.base.utils import (copy_tree, dict_merge, log, run_command,
                              set_attrs, shell_out)
from cyder.base.vcs import GitRepo

from cyder.core.utils import fail_mail
from cyder.core.ctnr.models import Ctnr
from cyder.cydhcp.network.models import Network
from cyder.cydhcp.vrf.models import Vrf
from cyder.cydhcp.workgroup.models import Workgroup

from cyder.settings import DHCPBUILD


class DHCPBuilder(MutexMixin):
    def __init__(self, *args, **kwargs):
        kwargs = dict_merge(DHCPBUILD, {
            'verbose': True,
            'debug': False,
        }, kwargs)
        set_attrs(self, kwargs)

        if self.log_syslog:
            syslog.openlog(b'dhcp_build', 0, syslog.LOG_LOCAL6)

        self.repo = GitRepo(self.prod_repo, self.line_change_limit,
            self.line_removal_limit, debug=self.debug,
            log_syslog=self.log_syslog, logger=syslog)

    def log_debug(self, msg, to_stderr=None):
        if to_stderr is None:
            to_stderr = self.debug
        log(msg, log_level='LOG_DEBUG', to_syslog=False, to_stderr=to_stderr,
                logger=syslog)

    def log_info(self, msg, to_stderr=None):
        if to_stderr is None:
            to_stderr = self.verbose
        log(msg, log_level='LOG_INFO', to_syslog=self.log_syslog,
                to_stderr=to_stderr, logger=syslog)

    def log_notice(self, msg, to_stderr=None):
        if to_stderr is None:
            to_stderr = self.verbose
        log(msg, log_level='LOG_NOTICE', to_syslog=self.log_syslog,
                to_stderr=to_stderr, logger=syslog)

    def log_err(self, msg, to_stderr=True):
        log(msg, log_level='LOG_ERR', to_syslog=self.log_syslog,
                to_stderr=to_stderr, logger=syslog)

    def run_command(self, command, log=True, failure_msg=None):
        if log:
            command_logger = self.log_debug
            failure_logger = self.log_err
        else:
            command_logger = None
            failure_logger = None

        return run_command(command, command_logger=command_logger,
                           failure_logger=failure_logger,
                           failure_msg=failure_msg)

    def build(self):
        try:
            with open(self.stop_file) as stop_fd:
                now = time.time()
                contents = stop_fd.read()
            last = os.path.getmtime(self.stop_file)

            msg = ('The stop file ({0}) exists. Build canceled.\n'
                   'Reason for skipped build:\n'
                   '{1}'.format(self.stop_file, contents))
            self.log_notice(msg, to_stderr=False)
            if (self.stop_file_email_interval is not None and
                    now - last > self.stop_file_email_interval):
                os.utime(self.stop_file, (now, now))
                fail_mail(msg, subject="DHCP builds have stopped")

            raise Exception(msg)
        except IOError as e:
            if e.errno == 2:  # IOError: [Errno 2] No such file or directory
                pass
            else:
                raise

        self.log_info('Building...')

        try:
            with open(os.path.join(self.stage_dir4, self.target_file4), 'w') \
                    as f:
                for ctnr in Ctnr.objects.all():
                    f.write(ctnr.build_legacy_classes())
                for vrf in Vrf.objects.all():
                    f.write(vrf.build_vrf())
                for network in Network.objects.filter(enabled=True,
                        ip_type=IP_TYPE_4):
                    f.write(network.build_subnet())
                for workgroup in Workgroup.objects.all():
                    f.write(workgroup.build_workgroup())
        except:
            self.error()

        try:
            with open(os.path.join(self.stage_dir6, self.target_file6), 'w') \
                    as f:
                for ctnr in Ctnr.objects.all():
                    f.write(ctnr.build_legacy_classes())
                for vrf in Vrf.objects.all():
                    f.write(vrf.build_vrf())
                for network in Network.objects.filter(enabled=True,
                        ip_type=IP_TYPE_6):
                    f.write(network.build_subnet())
                for workgroup in Workgroup.objects.all():
                    f.write(workgroup.build_workgroup())
        except:
            self.error()

        self.check_syntax()

        self.log_info('DHCP build successful')

    def push(self, sanity_check=True):
        self.repo.reset_and_pull()

        try:
            copy_tree(self.stage_dir4, self.prod_dir4)
            copy_tree(self.stage_dir6, self.prod_dir6)
        except:
            self.repo.reset_to_head()
            raise

        self.repo.commit_and_push('Update config', sanity_check=sanity_check)

    def error(self):
        ei = sys.exc_info()
        exc_msg = ''.join(format_exception(*ei)).rstrip('\n')

        self.log_err(
            'DHCP build failed.\nOriginal exception: ' + exc_msg,
            to_stderr=False)
        raise

    def check_syntax(self):
        def syntax_error(err):
            log_msg = 'DHCP build failed due to a syntax error'
            exception_msg = log_msg + ('\n{0} said:\n{1}'
                                       .format(self.dhcpd, err))

            self.log_err(log_msg, to_stderr=False)
            raise Exception(exception_message)

        if self.check_file4:
            out4, err4, ret4 = run_command("{0} -4 -t -cf {1}".format(
                self.dhcpd, os.path.join(self.stage_dir4, self.check_file4)
            ))

            if ret4 != 0:
                syntax_error(err4)

        if self.check_file6:
            out6, err6, ret6 = run_command("{0} -6 -t -cf {1}".format(
                self.dhcpd, os.path.join(self.stage_dir6, self.check_file6)
            ))

            if ret6 != 0:
                syntax_error(err6)

    def _lock_failure(self, pid):
        self.log_err(
            'Failed to acquire lock on {0}. Process {1} currently '
            'has it.'.format(self.lock_file, pid),
            to_stderr=False)
        fail_mail(
            'An attempt was made to start the DHCP build script while an '
            'instance of the script was already running. The attempt was '
            'denied.',
            subject="Concurrent DHCP builds attempted.")
        super(DHCPBuilder, self)._lock_failure(pid)
