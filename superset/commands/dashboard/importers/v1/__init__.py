# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from typing import Any

from collections import defaultdict
from marshmallow import Schema
from sqlalchemy.sql import select

from superset import db
from superset.charts.schemas import ImportV1ChartSchema
from superset.commands.chart.importers.v1.utils import import_chart
from superset.commands.dashboard.exceptions import DashboardImportError
from superset.commands.dashboard.importers.v1.utils import (
    find_chart_uuids,
    find_native_filter_datasets,
    import_dashboard,
    update_id_refs,
)
from superset.utils.core import get_user
from superset.commands.database.importers.v1.utils import import_database
from superset.commands.dataset.importers.v1.utils import import_dataset
from superset.commands.importers.v1 import ImportModelsCommand
from superset.daos.dashboard import DashboardDAO
from superset.dashboards.schemas import ImportV1DashboardSchema
from superset.databases.schemas import ImportV1DatabaseSchema
from superset.datasets.schemas import ImportV1DatasetSchema
from superset.migrations.shared.native_filters import migrate_dashboard
from superset.models.dashboard import Dashboard, dashboard_slices


class ImportDashboardsCommand(ImportModelsCommand):

    """Import dashboards"""

    dao = DashboardDAO
    model_name = "dashboard"
    prefix = "dashboards/"
    schemas: dict[str, Schema] = {
        "charts/": ImportV1ChartSchema(),
        "dashboards/": ImportV1DashboardSchema(),
        "datasets/": ImportV1DatasetSchema(),
        "databases/": ImportV1DatabaseSchema(),
    }
    import_error = DashboardImportError

    # TODO (betodealmeida): refactor to use code from other commands
    # pylint: disable=too-many-branches, too-many-locals
    @staticmethod
    def _import(configs: dict[str, Any], overwrite: bool = False) -> None:
        # discover charts and datasets associated with dashboards
        chart_uuids: set[str] = set()
        dataset_uuids: set[str] = set()
        for file_name, config in configs.items():
            if file_name.startswith("dashboards/"):
                chart_uuids.update(find_chart_uuids(config["position"]))
                dataset_uuids.update(
                    find_native_filter_datasets(config.get("metadata", {}))
                )

        # discover datasets associated with charts
        for file_name, config in configs.items():
            if file_name.startswith("charts/") and config["uuid"] in chart_uuids:
                dataset_uuids.add(config["dataset_uuid"])

        # discover databases associated with datasets
        database_uuids: set[str] = set()
        for file_name, config in configs.items():
            if file_name.startswith("datasets/") and config["uuid"] in dataset_uuids:
                database_uuids.add(config["database_uuid"])

        # import related databases
        database_ids: dict[str, int] = {}
        for file_name, config in configs.items():
            if file_name.startswith("databases/") and config["uuid"] in database_uuids:
                database = import_database(config, overwrite=False)
                database_ids[str(database.uuid)] = database.id

        # import datasets with the correct parent ref
        dataset_info: dict[str, dict[str, Any]] = {}
        for file_name, config in configs.items():
            if (
                file_name.startswith("datasets/")
                and config["database_uuid"] in database_ids
            ):
                config["database_id"] = database_ids[config["database_uuid"]]
                dataset = import_dataset(config, overwrite=False)
                dataset_info[str(dataset.uuid)] = {
                    "datasource_id": dataset.id,
                    "datasource_type": dataset.datasource_type,
                    "datasource_name": dataset.table_name,
                }

        # import charts with the correct parent ref
        charts = []
        chart_ids: dict[str, int] = {}
        for file_name, config in configs.items():
            if (
                file_name.startswith("charts/")
                and config["dataset_uuid"] in dataset_info
            ):
                # update datasource id, type, and name
                dataset_dict = dataset_info[config["dataset_uuid"]]
                config.update(dataset_dict)
                # pylint: disable=line-too-long
                dataset_uid = f"{dataset_dict['datasource_id']}__{dataset_dict['datasource_type']}"
                config["params"].update({"datasource": dataset_uid})
                if "query_context" in config:
                    config["query_context"] = None

                chart = import_chart(config, overwrite=False)
                charts.append(chart)
                chart_ids[str(chart.uuid)] = chart.id

        # store the existing relationship between dashboards and charts
        existing_relationships = db.session.execute(
            select([dashboard_slices.c.dashboard_id, dashboard_slices.c.slice_id])
        ).fetchall()

        # import dashboards
        dashboards: list[Dashboard] = []
        dashboard_chart_ids: list[tuple[int, int]] = []
        for file_name, config in configs.items():
            if file_name.startswith("dashboards/"):
                config = update_id_refs(config, chart_ids, dataset_info)
                dashboard = import_dashboard(config, overwrite=overwrite)
                dashboards.append(dashboard)
                for uuid in find_chart_uuids(config["position"]):
                    if uuid not in chart_ids:
                        break
                    chart_id = chart_ids[uuid]
                    if (dashboard.id, chart_id) not in existing_relationships:
                        dashboard_chart_ids.append((dashboard.id, chart_id))

        # set ref in the dashboard_slices table
        values = [
            {"dashboard_id": dashboard_id, "slice_id": chart_id}
            for (dashboard_id, chart_id) in dashboard_chart_ids
        ]
        db.session.execute(dashboard_slices.insert(), values)

        # Migrate any filter-box charts to native dashboard filters.
        for dashboard in dashboards:
            migrate_dashboard(dashboard)

        # Remove all obsolete filter-box charts.
        for chart in charts:
            if chart.viz_type == "filter_box":
                db.session.delete(chart)


class MedbiImportDashboardsCommand(ImportModelsCommand):

    """Import dashboards"""

    dao = DashboardDAO
    model_name = "dashboard"
    prefix = "dashboards/"
    schemas: dict[str, Schema] = {
        "charts/": ImportV1ChartSchema(),
        "dashboards/": ImportV1DashboardSchema(),
        "datasets/": ImportV1DatasetSchema(),
        "databases/": ImportV1DatabaseSchema(),
    }
    import_error = DashboardImportError

    def __init__(self, contents, postgres_database_id: int, clickhouse_database_id: int, **kwargs):
        self.postgres_database_id = postgres_database_id
        self.clickhouse_database_id = clickhouse_database_id
        super(MedbiImportDashboardsCommand, self).__init__(contents, **kwargs)

    # pylint: disable=too-many-branches, too-many-locals
    def _import(
        self,
        configs: dict[str, Any],
        overwrite: bool = False
    ) -> None:
        # discover charts and datasets associated with dashboards
        chart_uuids: set[str] = set()
        chart_uuids_map: dict[str, str] = {}
        dataset_uuids: set[str] = set()

        for file_name, config in configs.items():
            if file_name.startswith("dashboards/"):
                chart_uuids.update(find_chart_uuids(config["position"]))
                dataset_uuids.update(
                    find_native_filter_datasets(config.get("metadata", {}))
                )

        # discover datasets associated with charts
        for file_name, config in configs.items():
            if file_name.startswith("charts/") and config["uuid"] in chart_uuids:
                dataset_uuids.add(config["dataset_uuid"])

        # discover databases associated with datasets
        database_uuids: set[str] = set()
        database_datasets_count = defaultdict(lambda: 0)
        for file_name, config in configs.items():
            if file_name.startswith("datasets/") and config["uuid"] in dataset_uuids:
                database_uuid = config["database_uuid"]
                database_uuids.add(database_uuid)
                database_datasets_count[database_uuid] += 1

        # import related databases
        database_ids: dict[str, int] = {}
        for file_name, config in configs.items():
            if file_name.startswith("databases/") and config["uuid"] in database_uuids:
                is_clickhouse = 'clickhouse' in config['sqlalchemy_uri']
                database_ids[config['uuid']] = self.clickhouse_database_id \
                    if is_clickhouse else self.postgres_database_id
        assert len(database_ids) <= 2, database_ids

        # import datasets with the correct parent ref
        dataset_info: dict[str, dict[str, Any]] = {}
        dataset_old_ids_mapping: dict[int, str] = {}
        for file_name, config in configs.items():
            if (
                file_name.startswith("datasets/")
                and config["database_uuid"] in database_ids
            ):
                config["database_id"] = database_ids[config["database_uuid"]]
                origin_uuid = config['uuid']
                origin_id = config['id']
                dataset_old_ids_mapping[origin_id] = origin_uuid
                dataset = import_dataset(config, overwrite=True)
                dataset_info[origin_uuid] = {
                    "datasource_id": dataset.id,
                    "datasource_type": dataset.datasource_type,
                    "datasource_name": dataset.table_name,
                    "dataset_uuid": dataset.uuid
                }

        # import charts with the correct parent ref
        chart_ids: dict[str, int] = {}
        for file_name, config in configs.items():
            if (
                file_name.startswith("charts/")
                and config["dataset_uuid"] in dataset_info
            ):
                # update datasource id, type, and name
                origin_uuid = config['uuid']
                config.update(dataset_info[config["dataset_uuid"]])
                chart = import_chart(config, overwrite=True)
                chart_ids[origin_uuid] = chart.id
                chart_uuids_map[origin_uuid] = str(chart.uuid)

        # import dashboards
        dashboard_chart_ids: list[tuple[int, int]] = []
        for file_name, config in configs.items():
            if file_name.startswith("dashboards/"):

                rel_chart_ids = set()
                for uuid in find_chart_uuids(config["position"]):
                    if uuid not in chart_ids:
                        continue
                    chart_id = chart_ids[uuid]
                    rel_chart_ids.add(chart_id)

                config = update_id_refs(config, chart_ids, chart_uuids_map, dataset_info,
                                        dataset_old_id_to_uuid_mapping=dataset_old_ids_mapping)

                user = get_user()
                dashboard = import_dashboard(config, overwrite=overwrite, created_by_fk=user.id)

                # store the existing relationship between dashboards and charts
                existing_relationships = db.session.execute(
                    select(
                        [dashboard_slices.c.dashboard_id, dashboard_slices.c.slice_id])
                        .filter(dashboard_slices.c.dashboard_id == dashboard.id)
                ).fetchall()

                for chart_id in rel_chart_ids:
                    if (dashboard.id, chart_id) not in existing_relationships:
                        dashboard_chart_ids.append((dashboard.id, chart_id))

        # set ref in the dashboard_slices table
        values = [
            {"dashboard_id": dashboard_id, "slice_id": chart_id}
            for (dashboard_id, chart_id) in dashboard_chart_ids
        ]
        db.session.execute(dashboard_slices.insert(), values)


def update_id_refs(  # pylint: disable=too-many-locals
    config: dict[str, Any],
    chart_ids: dict[str, int],
    chart_uuids: dict[str, str],
    dataset_info: dict[str, dict[str, Any]],
    dataset_old_id_to_uuid_mapping: dict[int, str] = None
) -> dict[str, Any]:
    """Update dashboard metadata to use new IDs"""
    import json

    from .utils import  build_uuid_to_id_map
    fixed = config.copy()

    # build map old_id => new_id
    old_ids = build_uuid_to_id_map(fixed["position"])
    id_map = {
        old_id: chart_ids[uuid] for uuid, old_id in old_ids.items() if uuid in chart_ids
    }

    # fix metadata
    metadata = fixed.get("metadata", {})
    if "timed_refresh_immune_slices" in metadata:
        metadata["timed_refresh_immune_slices"] = [
            id_map[old_id] for old_id in metadata["timed_refresh_immune_slices"]
        ]

    if "filter_scopes" in metadata:
        # in filter_scopes the key is the chart ID as a string; we need to update
        # them to be the new ID as a string:
        metadata["filter_scopes"] = {
            str(id_map[int(old_id)]): columns
            for old_id, columns in metadata["filter_scopes"].items()
            #if int(old_id) in id_map
        }

        # now update columns to use new IDs:
        for columns in metadata["filter_scopes"].values():
            for attributes in columns.values():
                attributes["immune"] = [
                    id_map[old_id]
                    for old_id in attributes["immune"]
                    #if old_id in id_map
                ]

    if "expanded_slices" in metadata:
        metadata["expanded_slices"] = {
            str(id_map[int(old_id)]): value
            for old_id, value in metadata["expanded_slices"].items()
        }

    if "default_filters" in metadata:
        default_filters = json.loads(metadata["default_filters"])
        metadata["default_filters"] = json.dumps(
            {
                str(id_map[int(old_id)]): value
                for old_id, value in default_filters.items()
                #if int(old_id) in id_map
            }
        )

    # fix position
    position = fixed.get("position", {})
    for child in position.values():
        if (
            isinstance(child, dict)
            and child["type"] == "CHART"
            and "uuid" in child["meta"]
        ):
            try:
                child["meta"]["chartId"] = chart_ids[child["meta"]["uuid"]]
                child["meta"]["uuid"] = chart_uuids[child["meta"]["uuid"]]
            except Exception as e:
                pass

    # fix native filter references
    native_filter_configuration = fixed.get("metadata", {}).get(
        "native_filter_configuration", []
    )
    for native_filter in native_filter_configuration:
        targets = native_filter.get("targets", [])
        for target in targets:
            dataset_uuid = target.pop("datasetUuid", None)
            if not dataset_uuid:
                dataset_id = target.pop("datasetId", None)
                if dataset_id and dataset_old_id_to_uuid_mapping:
                    dataset_uuid = dataset_old_id_to_uuid_mapping[dataset_id]
            if dataset_uuid:
                target["datasetId"] = dataset_info[dataset_uuid]["datasource_id"]

        scope_excluded = native_filter.get("scope", {}).get("excluded", [])
        if scope_excluded:
            native_filter["scope"]["excluded"] = [
                id_map[old_id] for old_id in scope_excluded if old_id in id_map
            ]

    return fixed
