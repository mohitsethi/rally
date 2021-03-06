# Copyright 2013: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Tests for the Test engine."""

import mock

from rally.benchmark import engine
from rally.benchmark import validation
from rally import consts
from rally import exceptions
from tests import fakes
from tests import test


class BenchmarkEngineTestCase(test.TestCase):

    def setUp(self):
        super(BenchmarkEngineTestCase, self).setUp()

        self.valid_test_config_continuous_times = {
            'NovaServers.boot_and_delete_server': [
                {'args': {'flavor_id': 1, 'image_id': 'img'},
                 'execution': 'continuous',
                 'config': {'times': 10, 'active_users': 2,
                            'tenants': 3, 'users_per_tenant': 2}}
            ]
        }
        self.valid_test_config_continuous_duration = {
            'NovaServers.boot_and_delete_server': [
                {'args': {'flavor_id': 1, 'image_id': 'img'},
                 'execution': 'continuous',
                 'config': {'duration': 4, 'active_users': 2,
                            'tenants': 3, 'users_per_tenant': 2}}
            ]
        }
        self.invalid_test_config_bad_execution_type = {
            'NovaServers.boot_and_delete_server': [
                {'args': {'flavor_id': 1, 'image_id': 'img'},
                 'execution': 'contitnuous',
                 'config': {'times': 10, 'active_users': 2,
                            'tenants': 3, 'users_per_tenant': 2}}
            ]
        }
        self.invalid_test_config_bad_config_parameter = {
            'NovaServers.boot_and_delete_server': [
                {'args': {'flavor_id': 1, 'image_id': 'img'},
                 'execution': 'continuous',
                 'config': {'times': 10, 'activeusers': 2,
                            'tenants': 3, 'users_per_tenant': 2}}
            ]
        }
        self.invalid_test_config_parameters_conflict = {
            'NovaServers.boot_and_delete_server': [
                {'args': {'flavor_id': 1, 'image_id': 'img'},
                 'execution': 'continuous',
                 'config': {'times': 10, 'duration': 100,
                            'tenants': 3, 'users_per_tenant': 2}}
            ]
        }
        self.invalid_test_config_bad_param_for_periodic = {
            'NovaServers.boot_and_delete_server': [
                {'args': {'flavor_id': 1, 'image_id': 'img'},
                 'execution': 'periodic',
                 'config': {'times': 10, 'active_users': 3,
                            'tenants': 3, 'users_per_tenant': 2}}
            ]
        }
        self.valid_endpoints = [{
            'auth_url': 'http://127.0.0.1:5000/v2.0',
            'username': 'admin',
            'password': 'admin',
            'tenant_name': 'admin',
            'permission': consts.EndpointPermission.ADMIN
        }]

        self.run_success = {'msg': 'msg', 'status': 0, 'proc_name': 'proc'}

    def test__validate_config(self):
        try:
            engine.BenchmarkEngine(self.valid_test_config_continuous_times,
                                   mock.MagicMock())
            engine.BenchmarkEngine(self.valid_test_config_continuous_duration,
                                   mock.MagicMock())
        except Exception as e:
            self.fail("Unexpected exception in test config" +
                      "verification: %s" % str(e))
        self.assertRaises(exceptions.InvalidConfigException,
                          engine.BenchmarkEngine,
                          self.invalid_test_config_bad_execution_type,
                          mock.MagicMock())
        self.assertRaises(exceptions.InvalidConfigException,
                          engine.BenchmarkEngine,
                          self.invalid_test_config_bad_config_parameter,
                          mock.MagicMock())
        self.assertRaises(exceptions.InvalidConfigException,
                          engine.BenchmarkEngine,
                          self.invalid_test_config_parameters_conflict,
                          mock.MagicMock())
        self.assertRaises(exceptions.InvalidConfigException,
                          engine.BenchmarkEngine,
                          self.invalid_test_config_bad_param_for_periodic,
                          mock.MagicMock())

    @mock.patch("rally.benchmark.scenarios.base.Scenario.get_by_name")
    @mock.patch("rally.benchmark.engine.users_ctx")
    @mock.patch("rally.benchmark.utils.create_openstack_clients")
    @mock.patch("rally.benchmark.engine.BenchmarkEngine._validate_config")
    def test__validate_scenario_args(self, mock_validate_config,
                                     mock_create_os_clients,
                                     mock_user_ctxt,
                                     mock_scenario_get_by_name):

        @validation.requires_permission(consts.EndpointPermission.ADMIN)
        def validator_admin(**kwargs):
            return validation.ValidationResult()

        @validation.requires_permission(consts.EndpointPermission.USER)
        def validator_user(**kwargs):
            return validation.ValidationResult()

        FakeScenario = mock.MagicMock()
        FakeScenario.do_it.validators = [validator_admin, validator_user]
        mock_scenario_get_by_name.return_value = FakeScenario

        mock_user_ctxt.UserGenerator = fakes.FakeUserContext

        benchmark_engine = engine.BenchmarkEngine(mock.MagicMock(),
                                                  mock.MagicMock())
        benchmark_engine.admin_endpoint = "admin"

        benchmark_engine._validate_scenario_args("FakeScenario.do_it", {})

        expected = [mock.call("admin"),
                    mock.call(fakes.FakeUserContext.user["endpoint"])]
        mock_create_os_clients.assert_has_calls(expected, any_order=True)

    @mock.patch("rally.benchmark.scenarios.base.Scenario.get_by_name")
    @mock.patch("rally.benchmark.engine.users_ctx")
    @mock.patch("rally.benchmark.engine.osclients.Clients")
    @mock.patch("rally.benchmark.engine.BenchmarkEngine._validate_config")
    def test__validate_scenario_args_failure(self, mock_validate_config,
                                             mock_create_os_clients,
                                             mock_user_ctxt,
                                             mock_scenario_get_by_name):

        @validation.requires_permission(consts.EndpointPermission.ADMIN)
        def evil_validator_admin(**kwargs):
            return validation.ValidationResult(is_valid=False)

        FakeScenario = mock.MagicMock()
        FakeScenario.do_it.validators = [evil_validator_admin]
        mock_scenario_get_by_name.return_value = FakeScenario

        benchmark_engine = engine.BenchmarkEngine(mock.MagicMock(),
                                                  mock.MagicMock())
        benchmark_engine.admin_endpoint = "admin"

        self.assertRaises(exceptions.InvalidScenarioArgument,
                          benchmark_engine._validate_scenario_args,
                          "FakeScenario.do_it", {})

        mock_user_ctxt.UserGenerator = fakes.FakeUserContext

        @validation.requires_permission(consts.EndpointPermission.USER)
        def evil_validator_user(**kwargs):
            return validation.ValidationResult(is_valid=False)

        FakeScenario.do_it.validators = [evil_validator_user]

        self.assertRaises(exceptions.InvalidScenarioArgument,
                          benchmark_engine._validate_scenario_args,
                          "FakeScenario.do_it", {})

    @mock.patch("rally.benchmark.engine.osclients")
    def test_bind(self, mock_osclients):
        mock_osclients.Clients.return_value = fakes.FakeClients()
        benchmark_engine = engine.BenchmarkEngine(
            self.valid_test_config_continuous_times, mock.MagicMock())
        with benchmark_engine.bind(self.valid_endpoints):
            endpoint_dicts = [endpoint.to_dict(include_permission=True)
                              for endpoint in benchmark_engine.endpoints]
            self.assertEqual(endpoint_dicts, self.valid_endpoints)

    @mock.patch("rally.benchmark.engine.BenchmarkEngine."
                "_validate_scenario_args")
    @mock.patch("rally.benchmark.runners.base.ScenarioRunner.run")
    @mock.patch("rally.benchmark.utils.osclients")
    @mock.patch("rally.benchmark.engine.osclients")
    def test_run(self, mock_engine_osclients, mock_utils_osclients, mock_run,
                 mock_validate_scenario_args):
        mock_engine_osclients.Clients.return_value = fakes.FakeClients()
        mock_utils_osclients.Clients.return_value = fakes.FakeClients()
        benchmark_engine = engine.BenchmarkEngine(
            self.valid_test_config_continuous_times, mock.MagicMock())
        with benchmark_engine.bind(self.valid_endpoints):
            benchmark_engine.run()

    @mock.patch("rally.benchmark.engine.BenchmarkEngine."
                "_validate_scenario_args")
    @mock.patch("rally.benchmark.runners.base.ScenarioRunner.run")
    @mock.patch("rally.benchmark.utils.osclients")
    @mock.patch("rally.benchmark.engine.osclients")
    def test_task_status_basic_chain(self, mock_engine_osclients,
                                     mock_utils_osclients, mock_scenario_run,
                                     mock_validate_scenario_args):
        fake_task = mock.MagicMock()
        benchmark_engine = engine.BenchmarkEngine(
            self.valid_test_config_continuous_times, fake_task)
        mock_engine_osclients.Clients.return_value = fakes.FakeClients()
        mock_utils_osclients.Clients.return_value = fakes.FakeClients()
        mock_scenario_run.return_value = {}
        with benchmark_engine.bind(self.valid_endpoints):
            benchmark_engine.run()

        benchmark_name = 'NovaServers.boot_and_delete_server'
        benchmark_results = {
            'name': benchmark_name, 'pos': 0,
            'kw': self.valid_test_config_continuous_times[benchmark_name][0],
        }

        s = consts.TaskStatus
        expected = [
            mock.call.update_status(s.TEST_TOOL_BENCHMARKING),
            mock.call.append_results(benchmark_results, {'raw': {},
                                     'validation': {'is_valid': True}}),
            mock.call.update_status(s.FINISHED)
        ]
        # NOTE(msdubov): Ignore task['uuid'] calls which are used for logging
        mock_calls = filter(lambda call: '__getitem__' not in call[0],
                            fake_task.mock_calls)
        self.assertEqual(mock_calls, expected)

    @mock.patch("rally.benchmark.engine.BenchmarkEngine."
                "_validate_scenario_args")
    @mock.patch("rally.benchmark.runners.base.ScenarioRunner.run")
    @mock.patch("rally.benchmark.utils.osclients")
    @mock.patch("rally.benchmark.engine.osclients")
    def test_task_status_basic_chain_validation_fails(self,
                                                      mock_engine_osclients,
                                                      mock_utils_osclients,
                                                      mock_scenario_run,
                                                      mock_validate_sc_args):
        fake_task = mock.MagicMock()
        benchmark_engine = engine.BenchmarkEngine(
            self.valid_test_config_continuous_times, fake_task)
        mock_engine_osclients.Clients.return_value = fakes.FakeClients()
        mock_utils_osclients.Clients.return_value = fakes.FakeClients()
        validation_exc = exceptions.InvalidScenarioArgument()
        mock_validate_sc_args.side_effect = validation_exc

        with benchmark_engine.bind(self.valid_endpoints):
            benchmark_engine.run()

        benchmark_name = 'NovaServers.boot_and_delete_server'
        benchmark_results = {
            'name': benchmark_name, 'pos': 0,
            'kw': self.valid_test_config_continuous_times[benchmark_name][0],
        }

        s = consts.TaskStatus
        expected = [
            mock.call.update_status(s.TEST_TOOL_BENCHMARKING),
            mock.call.append_results(benchmark_results,
                                     {'raw': [],
                                      'validation': {'is_valid': False,
                                      'exc_msg': validation_exc.message}}),
            mock.call.set_failed(),
            mock.call.update_status(s.FINISHED)
        ]
        # NOTE(msdubov): Ignore task['uuid'] calls which are used for logging
        mock_calls = filter(lambda call: '__getitem__' not in call[0],
                            fake_task.mock_calls)
        self.assertEqual(mock_calls, expected)

    @mock.patch("rally.benchmark.engine.BenchmarkEngine."
                "_validate_scenario_args")
    @mock.patch("rally.benchmark.runners.base.ScenarioRunner.run")
    @mock.patch("rally.benchmark.utils.osclients")
    @mock.patch("rally.benchmark.engine.osclients")
    def test_task_status_failed(self, mock_engine_osclients,
                                mock_utils_osclients, mock_scenario_run,
                                mock_validate_scenario_args):
        fake_task = mock.MagicMock()
        benchmark_engine = engine.BenchmarkEngine(
            self.valid_test_config_continuous_times, fake_task)
        mock_engine_osclients.Clients.return_value = fakes.FakeClients()
        mock_utils_osclients.Clients.return_value = fakes.FakeClients()
        mock_scenario_run.side_effect = exceptions.TestException()
        try:
            with benchmark_engine.bind(self.valid_endpoints):
                benchmark_engine.run()
        except exceptions.TestException:
            pass

        s = consts.TaskStatus
        expected = [
            mock.call.update_status(s.TEST_TOOL_BENCHMARKING),
            mock.call.set_failed(),
        ]
        # NOTE(msdubov): Ignore task['uuid'] calls which are used for logging
        mock_calls = filter(lambda call: '__getitem__' not in call[0],
                            fake_task.mock_calls)
        self.assertEqual(mock_calls, expected)
