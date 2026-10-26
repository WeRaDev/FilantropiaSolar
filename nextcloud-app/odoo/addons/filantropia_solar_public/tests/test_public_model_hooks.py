"""Isolated tests for Odoo snapshot and website lead hooks (no Odoo runtime)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

ADDON_ROOT = Path(__file__).resolve().parents[1]
_NAMESPACE = "_fs_public_model_hooks_test"


def _identity_decorator(function=None):
    if function is None:
        return lambda decorated: decorated
    return function


class _Field:
    pass


class _DateTimeField:
    def __new__(cls, *_args, **_kwargs):
        return _Field()

    @staticmethod
    def now():
        return datetime(2026, 9, 28, 16, 0, tzinfo=UTC).replace(tzinfo=None)


class _OdooModel:
    def create(self, values):
        return self._test_super_create(values)

    def write(self, values):
        return self._test_super_write(values)


class _Constraint:
    def __init__(self, definition, message=""):
        self.definition = definition
        self.message = message


def _install_odoo_stubs():
    existing = sys.modules.get("odoo")
    if existing is not None and hasattr(existing, "__path__"):
        raise unittest.SkipTest("These isolated tests run without an Odoo runtime")

    odoo = existing or types.ModuleType("odoo")
    odoo.api = types.SimpleNamespace(
        model=_identity_decorator,
        model_create_multi=_identity_decorator,
    )

    def field_factory(*_args, **_kwargs):
        return _Field()

    odoo.fields = types.SimpleNamespace(
        Boolean=field_factory,
        Char=field_factory,
        Float=field_factory,
        Integer=field_factory,
        Json=field_factory,
        Many2one=field_factory,
        Selection=field_factory,
        Text=field_factory,
        Datetime=_DateTimeField,
    )
    odoo.models = types.SimpleNamespace(Model=_OdooModel, Constraint=_Constraint)

    http_module = sys.modules.get("odoo.http") or types.ModuleType("odoo.http")

    class _Controller:
        pass

    def route(*_args, **_kwargs):
        return _identity_decorator

    http_module.Controller = _Controller
    http_module.route = route
    http_module.request = None
    odoo.http = types.SimpleNamespace(Controller=_Controller, route=route)
    sys.modules["odoo"] = odoo
    sys.modules["odoo.http"] = http_module

    if "markupsafe" not in sys.modules:
        markupsafe = types.ModuleType("markupsafe")
        markupsafe.Markup = str
        sys.modules["markupsafe"] = markupsafe


def _ensure_package(name: str, path: Path):
    package = sys.modules.get(name)
    if package is None:
        package = types.ModuleType(name)
        package.__path__ = [str(path)]
        sys.modules[name] = package
    return package


def _load_module(name: str, path: Path):
    module = sys.modules.get(name)
    if module is not None:
        return module
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load test module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_addon_modules():
    _install_odoo_stubs()
    _ensure_package(_NAMESPACE, ADDON_ROOT)
    for child in ("controllers", "models", "services"):
        _ensure_package(f"{_NAMESPACE}.{child}", ADDON_ROOT / child)

    controller = _load_module(
        f"{_NAMESPACE}.controllers.main",
        ADDON_ROOT / "controllers" / "main.py",
    )
    snapshot = _load_module(
        f"{_NAMESPACE}.models.fs_public_snapshot",
        ADDON_ROOT / "models" / "fs_public_snapshot.py",
    )

    client_stub = types.ModuleType(f"{_NAMESPACE}.services.nc_lifecycle_client")

    class _NcLifecycleClient:
        pass

    class _NcLifecycleError(Exception):
        pass

    client_stub.NcLifecycleClient = _NcLifecycleClient
    client_stub.NcLifecycleError = _NcLifecycleError
    client_stub.redact_secrets = lambda value: value
    sys.modules[client_stub.__name__] = client_stub

    lead = _load_module(
        f"{_NAMESPACE}.models.crm_lead",
        ADDON_ROOT / "models" / "crm_lead.py",
    )
    return controller, snapshot, lead


class _SnapshotRow:
    def __init__(self, values):
        self.values = dict(values)
        self.write_calls = 0

    def write(self, values):
        self.values.update(values)
        self.write_calls += 1


class _SnapshotModel:
    def __init__(self, model_class, snapshot=None):
        self.model_class = model_class
        self.snapshot = snapshot
        self.created = []

    def cron_refresh_public_snapshot(self):
        return self.model_class.cron_refresh_public_snapshot(self)

    def sudo(self):
        return self

    def _get_current(self):
        return self.snapshot

    def create(self, values):
        self.created.append(dict(values))
        self.snapshot = _SnapshotRow(values)
        return self.snapshot


class PublicSnapshotCronTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.controller_module, cls.snapshot_module, _lead_module = _load_addon_modules()

    def _controller(self, *, dashboard_error=None):
        controller = self.controller_module.FilantropiaSolarPublicController()

        def fetch(endpoint):
            if endpoint == "stations":
                return {
                    "success": True,
                    "stations": [
                        {
                            "id": "station-1",
                            "name": "Public station",
                            "latitude": 41.15,
                            "longitude": -8.61,
                            "exact_latitude": 41.15,
                            "street": "Private street",
                            "capacity_kwp": 5.5,
                        }
                    ],
                }
            if dashboard_error:
                raise dashboard_error
            return {
                "success": True,
                "station_count": 1,
                "total_capacity_kwp": 5.5,
                "locations": ["Porto"],
            }

        controller._fetch_json = fetch
        return controller

    def test_refresh_persists_complete_public_enriched_snapshot(self):
        model = _SnapshotModel(self.snapshot_module.FsPublicSnapshot)
        controller = self._controller()

        with patch.object(
            self.snapshot_module,
            "FilantropiaSolarPublicController",
            return_value=controller,
        ):
            self.assertTrue(model.cron_refresh_public_snapshot())

        self.assertEqual(len(model.created), 1)
        saved = model.created[0]
        station = saved["stations_data"][0]
        self.assertNotEqual(station["latitude"], 41.15)
        self.assertNotIn("exact_latitude", station)
        self.assertNotIn("street", station)
        self.assertEqual(saved["dashboard_data"]["station_count"], 1)
        self.assertEqual(
            saved["refreshed_at"],
            datetime(2026, 9, 28, 16, 0),
        )

    def test_failed_partial_refresh_retains_previous_snapshot(self):
        old_values = {
            "stations_data": [{"id": "previous-complete-set"}],
            "dashboard_data": {"station_count": 9},
            "refreshed_at": datetime(2026, 9, 28, 12, 0),
        }
        snapshot = _SnapshotRow(old_values)
        model = _SnapshotModel(self.snapshot_module.FsPublicSnapshot, snapshot)
        controller = self._controller(
            dashboard_error=TimeoutError("Nextcloud dashboard unavailable")
        )

        with patch.object(
            self.snapshot_module,
            "FilantropiaSolarPublicController",
            return_value=controller,
        ):
            self.assertFalse(model.cron_refresh_public_snapshot())

        self.assertEqual(snapshot.write_calls, 0)
        self.assertEqual(snapshot.values, old_values)
        self.assertEqual(model.created, [])

    def test_invalid_stations_response_does_not_create_snapshot(self):
        model = _SnapshotModel(self.snapshot_module.FsPublicSnapshot)
        controller = self._controller()
        controller._fetch_json = lambda _endpoint: {"success": True}

        with patch.object(
            self.snapshot_module,
            "FilantropiaSolarPublicController",
            return_value=controller,
        ):
            self.assertFalse(model.cron_refresh_public_snapshot())

        self.assertIsNone(model.snapshot)
        self.assertEqual(model.created, [])


class _FakeCursor:
    def __init__(self):
        self.flags = set()
        self._row = None

    @contextmanager
    def savepoint(self):
        previous = set(self.flags)
        try:
            yield
        except Exception:
            self.flags = previous
            raise

    def execute(self, query, params):
        flag_name = re.search(r"SET ([a-z_]+) = TRUE", query).group(1)
        key = (params[0], flag_name)
        if key in self.flags:
            self._row = None
        else:
            self.flags.add(key)
            self._row = (params[0],)

    def fetchone(self):
        return self._row


class _FakePartner:
    def __init__(self, email):
        self.email = email

    def sudo(self):
        return self


class _FakeUser:
    def __init__(self, user_id, email, *, active=True, share=False):
        self.id = user_id
        self.partner_id = _FakePartner(email)
        self.active = active
        self.share = share

    def sudo(self):
        return self

    def exists(self):
        return self


class _EmptyRecordset:
    def __bool__(self):
        return False

    def exists(self):
        return self


class _FakeUsers:
    def __init__(self, users):
        self.users = users

    def sudo(self):
        return self

    def browse(self, user_id):
        return self.users.get(user_id, _EmptyRecordset())


class _FakeConfigParameters:
    def __init__(self, value):
        self.value = value

    def sudo(self):
        return self

    def get_param(self, _key):
        return self.value


class _FakeTemplate:
    def __init__(self):
        self.calls = []

    def sudo(self):
        return self

    def send_mail(self, lead_id, *, force_send, email_values):
        self.calls.append((lead_id, force_send, dict(email_values)))
        return len(self.calls)


class _FakeEnvironment:
    def __init__(self, qualified_stage, *, context=None):
        self.context = context or {}
        self.cr = _FakeCursor()
        self.admin = _FakeUser(1, "admin@example.test")
        self.qualified_user = _FakeUser(42, "dan@example.test")
        self.users = _FakeUsers({42: self.qualified_user})
        self.config = _FakeConfigParameters("42")
        self.qualified_stage = qualified_stage
        self.admin_template = _FakeTemplate()
        self.qualified_template = _FakeTemplate()

    def ref(self, xmlid, raise_if_not_found=True):
        refs = {
            "base.user_admin": self.admin,
            "crm.stage_lead2": self.qualified_stage,
            "filantropia_solar_public.mail_template_fs_website_lead_admin": (
                self.admin_template
            ),
            "filantropia_solar_public.mail_template_fs_lead_qualified": (
                self.qualified_template
            ),
        }
        result = refs.get(xmlid)
        if result is None and raise_if_not_found:
            raise KeyError(xmlid)
        return result

    def __getitem__(self, model_name):
        if model_name == "ir.config_parameter":
            return self.config
        if model_name == "res.users":
            return self.users
        if model_name == "res.partner":
            return _EmptyRecordset()
        raise KeyError(model_name)


class _FakeLeadRecord:
    def __init__(
        self,
        lead_class,
        lead_id,
        env,
        *,
        values=None,
        stage=None,
        lifecycle_state="virtual",
    ):
        self._lead_class = lead_class
        self.id = lead_id
        self.env = env
        self.stage_id = stage
        self.fs_website_origin = False
        self.fs_admin_notification_queued = False
        self.fs_qualified_notification_queued = False
        self.fs_nc_lifecycle_state = lifecycle_state
        self.fs_nc_public_archived = False
        self.fs_nc_installation_id = "station-1"
        self.fs_nc_db_id = 1
        for name, value in (values or {}).items():
            setattr(self, name, value)

    def ensure_one(self):
        return None

    def invalidate_recordset(self, *_args):
        return None

    def _fs_queue_notification(self, notification_type):
        return self._lead_class._fs_queue_notification(self, notification_type)

    def _fs_notification_email(self, notification_type):
        return self._lead_class._fs_notification_email(self, notification_type)


class _FakeLeadRecordsetBehavior:
    def __init__(self, lead_class, records, env):
        self._lead_class = lead_class
        self._records = records
        self.env = env

    def __iter__(self):
        return iter(self._records)

    def filtered(self, field_name):
        return self.__class__(
            self._lead_class,
            [record for record in self._records if getattr(record, field_name)],
            self.env,
        )

    def _test_super_write(self, values):
        for record in self._records:
            for name, value in values.items():
                setattr(record, name, value)
        return True


class _FakeLeadModelBehavior:
    def __init__(self, lead_class, env, recordset_class):
        self._lead_class = lead_class
        self.env = env
        self._recordset_class = recordset_class

    def _test_super_create(self, values_list):
        records = [
            _FakeLeadRecord(
                self._lead_class,
                index,
                self.env,
                values=values,
            )
            for index, values in enumerate(values_list, start=1)
        ]
        return self._recordset_class(self._lead_class, records, self.env)


class LeadNotificationHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _controller_module, _snapshot_module, cls.lead_module = _load_addon_modules()
        cls.recordset_class = type(
            "_FakeLeadRecordset",
            (cls.lead_module.CrmLead, _FakeLeadRecordsetBehavior),
            {},
        )
        cls.model_class = type(
            "_FakeLeadModel",
            (cls.lead_module.CrmLead, _FakeLeadModelBehavior),
            {},
        )
        cls.new_stage = types.SimpleNamespace(id=1, name="New", is_won=False)
        cls.qualified_stage = types.SimpleNamespace(
            id=2,
            name="Qualified",
            is_won=False,
        )

    def test_public_create_queues_admin_but_imported_create_does_not(self):
        env = _FakeEnvironment(self.qualified_stage)
        model = self.model_class(
            self.lead_module.CrmLead,
            env,
            self.recordset_class,
        )

        model.create(
            [
                {"fs_website_origin": True},
                {"fs_website_origin": False},
            ]
        )

        self.assertEqual(
            env.admin_template.calls,
            [(1, False, {"email_to": "admin@example.test"})],
        )
        self.assertEqual(env.qualified_template.calls, [])

    def test_create_context_can_suppress_notifications(self):
        env = _FakeEnvironment(
            self.qualified_stage,
            context={"fs_skip_notifications": True},
        )
        model = self.model_class(
            self.lead_module.CrmLead,
            env,
            self.recordset_class,
        )

        model.create([{"fs_website_origin": True}])

        self.assertEqual(env.admin_template.calls, [])

    def test_first_qualified_transition_queues_dan_once(self):
        env = _FakeEnvironment(self.qualified_stage)
        lead = _FakeLeadRecord(
            self.lead_module.CrmLead,
            7,
            env,
            values={"fs_website_origin": True},
            stage=self.new_stage,
        )
        recordset = self.recordset_class(self.lead_module.CrmLead, [lead], env)

        self.lead_module.CrmLead.write(recordset, {"stage_id": self.qualified_stage})
        self.lead_module.CrmLead.write(recordset, {"stage_id": self.qualified_stage})
        self.lead_module.CrmLead.write(recordset, {"stage_id": self.new_stage})
        self.lead_module.CrmLead.write(recordset, {"stage_id": self.qualified_stage})

        self.assertEqual(
            env.qualified_template.calls,
            [(7, False, {"email_to": "dan@example.test"})],
        )
        self.assertEqual(env.admin_template.calls, [])

    def test_reconciliation_context_suppresses_qualified_notice(self):
        env = _FakeEnvironment(
            self.qualified_stage,
            context={"fs_skip_notifications": True},
        )
        lead = _FakeLeadRecord(
            self.lead_module.CrmLead,
            8,
            env,
            values={"fs_website_origin": True},
            stage=self.new_stage,
        )
        recordset = self.recordset_class(self.lead_module.CrmLead, [lead], env)

        self.lead_module.CrmLead.write(recordset, {"stage_id": self.qualified_stage})

        self.assertEqual(env.qualified_template.calls, [])

    def test_imported_lead_qualified_transition_does_not_notify(self):
        env = _FakeEnvironment(self.qualified_stage)
        lead = _FakeLeadRecord(
            self.lead_module.CrmLead,
            9,
            env,
            stage=self.new_stage,
        )
        recordset = self.recordset_class(self.lead_module.CrmLead, [lead], env)

        self.lead_module.CrmLead.write(recordset, {"stage_id": self.qualified_stage})

        self.assertEqual(env.qualified_template.calls, [])


if __name__ == "__main__":
    unittest.main()
