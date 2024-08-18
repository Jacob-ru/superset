/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import { SafeMarkdown, styled, t } from '@superset-ui/core';
import Handlebars from 'handlebars';
import moment from 'moment';
import React, { useMemo, useState } from 'react';
import { isPlainObject } from 'lodash';
import Helpers from 'just-handlebars-helpers';

export interface HandlebarsViewerProps {
  templateSource: string;
  data: any;
}

export const HandlebarsViewer = ({
  templateSource,
  data,
}: HandlebarsViewerProps) => {
  const [renderedTemplate, setRenderedTemplate] = useState('');
  const [error, setError] = useState('');
  const appContainer = document.getElementById('app');
  const { common } = JSON.parse(
    appContainer?.getAttribute('data-bootstrap') || '{}',
  );
  const htmlSanitization = common?.conf?.HTML_SANITIZATION ?? true;
  const htmlSchemaOverrides =
    common?.conf?.HTML_SANITIZATION_SCHEMA_EXTENSIONS || {};

  useMemo(() => {
    try {
      const template = Handlebars.compile(templateSource);
      const result = template(data);
      setRenderedTemplate(result);
      setError('');
    } catch (error) {
      setRenderedTemplate('');
      setError(error.message);
    }
  }, [templateSource, data]);

  const Error = styled.pre`
    white-space: pre-wrap;
  `;

  if (error) {
    return <Error>{error}</Error>;
  }

  if (renderedTemplate) {
    return (
      <SafeMarkdown
        source={renderedTemplate}
        htmlSanitization={htmlSanitization}
        htmlSchemaOverrides={htmlSchemaOverrides}
      />
    );
  }
  return <p>{t('Loading...')}</p>;
};

//  usage: {{dateFormat my_date format="MMMM YYYY"}}
Handlebars.registerHelper('dateFormat', function (context, block) {
  const f = block.hash.format || 'YYYY-MM-DD';
  return moment(context).format(f);
});

// usage: {{  }}
Handlebars.registerHelper('stringify', (obj: any, obj2: any) => {
  // calling without an argument
  if (obj2 === undefined)
    throw Error('Please call with an object. Example: `stringify myObj`');
  return isPlainObject(obj) ? JSON.stringify(obj) : String(obj);
});

//
Handlebars.registerHelper('localeNumber', (number: any) =>
  Number(number).toLocaleString('ru-RU'),
);

Handlebars.registerHelper(
  'toMillions',
  (number: any) => `${(number / 1000000).toFixed(2)} млн.`,
);

Handlebars.registerHelper('toShortened', (number: any) => {
  if (Math.abs(number) >= 1000000)
    return `${(number / 1000000).toFixed(2)} млн.`;
  if (Math.abs(number) >= 1000) return `${(number / 1000).toFixed(2)} тыс.`;
  return `${number.toFixed(2)}`;
});

Handlebars.registerHelper(
  'toFixed',
  (number: any, digits: number) => `${number.toFixed(digits)}`,
);

Handlebars.registerHelper('countTotalSum', (values: any, digits) => {
  let sum: number;
  sum = 0;
  Object.values(values).forEach(function (value: number) {
    const isNumber = typeof value === 'number';

    if (isNumber) {
      sum += value;
    }
  });
  const isNumber = typeof sum === 'number';
  if (isNumber) {
    return sum.toFixed(digits);
  }
  return `NotANumber(${sum})`;
});

Handlebars.registerHelper(
  'countTotalListSum',
  (values: any, fieldName: string, digits) => {
    let sum: number;
    sum = 0;
    values.forEach(function (value: any, idx: number) {
      sum += value[fieldName];
    });
    const isNumber = (typeof sum) === 'number';
    if (isNumber) {
      return sum.toFixed(digits);
    }
    return `NotANumber(${sum})`;
  },
);

Helpers.registerHelpers(Handlebars);
