/*
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

import { utcFormat, timeFormat } from 'd3-time-format';
import { utcUtils, localTimeUtils } from '../utils/d3Time';
import TimeFormatter from '../TimeFormatter';

var d3 = typeof require === 'function' ? require('d3') : window.d3;

type FormatsByStep = Partial<{
  millisecond: string;
  second: string;
  minute: string;
  hour: string;
  day: string;
  week: string;
  month: string;
  year: string;
}>;

export default function createMultiFormatter({
  id,
  label,
  description,
  formats = {},
  useLocalTime = false,
}: {
  id: string;
  label?: string;
  description?: string;
  formats?: FormatsByStep;
  useLocalTime?: boolean;
}) {
  const {
    millisecond = '.%L',
    second = ':%S',
    minute = '%I:%M',
    hour = '%I %p',
    day = '%a %d',
    week = '%b %d',
    month = '%B',
    year = '%Y',
  } = formats;
  console.log('smart date formatter')
  // MEDBI: Локализация для русского языка в названии месяцев //
  const ru_RU = {
      "decimal": ",",
      "thousands": "\xa0",
      "grouping": [3],
      "currency": ["", " руб."],
      "dateTime": "%A, %e %B %Y г. %X",
      "date": "%d.%m.%Y",
      "time": "%H:%M:%S",
      "periods": ["AM", "PM"],
      "days": ["воскресенье", "понедельник", "вторник", "среда", "четверг", "пятница", "суббота"],
      "shortDays": ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"],
      "months": ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"],
      "shortMonths": ["Янв", "Фев", "Март", "Апр", "Май", "Июнь", "Июль", "Авг", "Сен", "Окт", "Нояб", "Дек"]
  };
  const timeFormat = d3.locale(ru_RU).timeFormat;
  const utcFormat = timeFormat;

  const format = useLocalTime ? timeFormat : utcFormat;
  const formatMillisecond = format(millisecond);
  const formatSecond = format(second);
  const formatMinute = format(minute);
  const formatHour = format(hour);
  const formatDay = format(day);
  const formatFirstDayOfWeek = format(week);
  const formatMonth = format(month);
  const formatYear = format(year);

  const {
    hasMillisecond,
    hasSecond,
    hasMinute,
    hasHour,
    isNotFirstDayOfMonth,
    isNotFirstDayOfWeek,
    isNotFirstMonth,
  } = useLocalTime ? localTimeUtils : utcUtils;

  function multiFormatFunc(date: Date) {
    if (hasMillisecond(date)) {
      return formatMillisecond;
    }
    if (hasSecond(date)) {
      return formatSecond;
    }
    if (hasMinute(date)) {
      return formatMinute;
    }
    if (hasHour(date)) {
      return formatHour;
    }
    if (isNotFirstDayOfMonth(date)) {
      return isNotFirstDayOfWeek(date) ? formatDay : formatFirstDayOfWeek;
    }
    if (isNotFirstMonth(date)) {
      return formatMonth;
    }

    return formatYear;
  }

  return new TimeFormatter({
    description,
    formatFunc: (date: Date) => multiFormatFunc(date)(date),
    id,
    label,
    useLocalTime,
  });
}
