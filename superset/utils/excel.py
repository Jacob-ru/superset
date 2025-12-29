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
import io
from decimal import Decimal
from typing import Any
from pandas.io.formats.excel import ExcelCell
import pandas as pd


def df_to_excel(df: pd.DataFrame, from_date = None, to_date=None, slice_name: str = None,
                **kwargs: Any) -> Any:
    output = io.BytesIO()

    # timezones are not supported
    for column in df.select_dtypes(include=["datetimetz"]).columns:
        df[column] = df[column].astype(str)

    for column in df.select_dtypes(include=["object"]).columns:
        def _decimal_to_float_with_comma_sep(v):
            if isinstance(v, Decimal):
                v = float(v)
            return v
        df[column] = df[column].map(_decimal_to_float_with_comma_sep)

    # pylint: disable=abstract-class-instantiated
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        if from_date and to_date:
            period_text = f'Период: {from_date.date()} - {to_date.date()}'
        else:
            period_text = ""
        graph_name = f"График: {slice_name}"
        writer._write_cells(
            [ExcelCell(col=0, row=0, val=period_text),
                   ExcelCell(col=0, row=1, val=graph_name),],
            sheet_name="Sheet1"
        )
        df.to_excel(writer, startrow=2, **kwargs)

    return output.getvalue()
