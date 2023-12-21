#
# BSD 3-Clause License
#
# Copyright (c) 2023, Fred W6BSD
# All rights reserved.
#
# pylint: disable=invalid-name

import dbm
import logging
import marshal
import os
import plistlib
import time
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from urllib.error import HTTPError
from urllib.request import urlretrieve

CTY_URL = "https://www.country-files.com/cty/cty.plist"
CTY_HOME = "/var/tmp"
CTY_FILE = "cty.plist"
CTY_DB = "cty.db"
CTY_EXPIRE = 86400 * 7          # One week

LRU_CACHE_SIZE = 8192


@dataclass(slots=True)
class DXCCRecord:  # pylint: disable=too-many-instance-attributes
  country: str
  prefix: str
  adif: int
  cqzone: int
  ituzone: int
  continent: str
  latitude: float
  longitude: float
  gmtoffset: int
  exactcallsign: bool

  def __init__(self, **kwargs):
    kwargs = {k.lower(): v for k, v in kwargs.items()}
    for key in DXCCRecord.__slots__:  # pylint: disable=no-member
      setattr(self, key, kwargs[key])


class DXCC:
  # pylint: disable=method-hidden

  def __init__(self, db_path=CTY_HOME, cache_size=LRU_CACHE_SIZE):
    self._entities = defaultdict(set)
    self._max_len = 0
    self._get_prefix = lru_cache(maxsize=cache_size)(self._get_prefix)
    self._db = os.path.join(os.path.expanduser(db_path), CTY_DB)
    cty_file = os.path.join(os.path.expanduser(db_path), CTY_FILE)

    try:
      fstat = os.stat(self._db)
      if fstat.st_mtime + CTY_EXPIRE > time.time():
        logging.info('Using DXCC cache %s', self._db)
        with dbm.open(self._db, 'r') as cdb:
          self._entities, self._max_len = marshal.loads(cdb['_meta_data_'])
        return
    except FileNotFoundError:
      logging.error('DXEntity cache not found')
    except dbm.error as err:
      logging.error(err)

    logging.info('Download %s', cty_file)
    self.load_cty(cty_file)
    with open(cty_file, 'rb') as fdc:
      cty_data = plistlib.load(fdc)
    self._max_len = max(len(k) for k in cty_data)

    logging.info('Create cty cache: %s', self._db)
    with dbm.open(self._db, 'c') as cdb:
      for key, val in cty_data.items():
        cdb[key] = marshal.dumps(val)
        self._entities[val['Country']].add(key)
      cdb['_meta_data_'] = marshal.dumps([dict(self._entities), self._max_len])

  def lookup(self, call):
    return self._get_prefix(call)

  def _get_prefix(self, call):
    call = call.upper()
    prefixes = list({call[:c] for c in range(self._max_len, 0, -1)})
    prefixes.sort(key=lambda x: -len(x))
    with dbm.open(self._db, 'r') as cdb:
      for prefix in prefixes:
        if prefix in cdb:
          return DXCCRecord(**marshal.loads(cdb[prefix]))
    raise KeyError(f"{call} not found")

  def cache_info(self):
    return self._get_prefix.cache_info()

  def isentity(self, country):
    if country in self._entities:
      return True
    return False

  @property
  def entities(self):
    return self._entities

  def get_entity(self, key):
    if key in self._entities:
      return self._entities[key]
    raise KeyError(f'Entity {key} not found')

  def __str__(self):
    return f"{self.__class__} {id(self)} ({self._db})"

  def __repr__(self):
    return str(self)

  @staticmethod
  def load_cty(cty_file):
    cty_tmp = cty_file + '.tmp'
    try:
      urlretrieve(CTY_URL, cty_tmp)
      if os.path.exists(cty_file):
        os.unlink(cty_file)
      os.rename(cty_tmp, cty_file)
    except HTTPError as err:
      logging.error(err)
      return