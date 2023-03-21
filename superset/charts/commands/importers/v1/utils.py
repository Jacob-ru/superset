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

import json
from uuid import uuid4
from typing import Any, Dict

from flask import g
from sqlalchemy.orm import Session

from superset.models.slice import Slice


def import_chart(
    session: Session, config: Dict[str, Any], overwrite: bool = False
) -> Slice:
    config = config.copy()
    existing = session.query(Slice).filter_by(uuid=config["uuid"]).first()
    datasource_id = config.get('datasource_id')
    if existing:
        if datasource_id and datasource_id != existing.datasource_id:
            existing = session.query(Slice).filter_by(datasource_id=datasource_id,
                                                      slice_name=config['slice_name'])\
                .all()

            if existing:
                existing = existing[0]
            else:
                existing = None

            if not existing:
                config['uuid'] = str(uuid4())
            else:
                config['uuid'] = str(existing.uuid)
    if existing:
        if not overwrite:
            return existing
        config["id"] = existing.id

    # TODO (betodealmeida): move this logic to import_from_dict
    config["params"] = json.dumps(config["params"])

    chart = Slice.import_from_dict(session, config, recursive=False)
    if chart.id is None:
        session.flush()

    if hasattr(g, "user") and g.user:
        chart.owners.append(g.user)

    return chart
