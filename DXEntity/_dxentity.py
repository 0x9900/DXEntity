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
from typing import Callable, DefaultDict
from urllib.error import HTTPError
from urllib.request import urlretrieve

CTY_URL = "https://www.country-files.com/cty/cty.plist"
CTY_HOME = "/var/tmp"
CTY_FILE = "cty.plist"
CTY_DB = "cty.db"
CTY_EXPIRE = 86400 * 7          # One week

LRU_CACHE_SIZE = 2048


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

  def __init__(self, db_path: str = CTY_HOME, cache_size: int = LRU_CACHE_SIZE,
               cache_expire: int = CTY_EXPIRE):
    cty_file: str = os.path.join(os.path.expanduser(db_path), CTY_FILE)

    self._max_len: int = 0
    self.get_prefix: Callable = lru_cache(maxsize=cache_size)(self._get_prefix)
    self._db: str = os.path.join(os.path.expanduser(db_path), CTY_DB)
    self._entities: DefaultDict[str, set] = defaultdict(set)

    try:
      fstat = os.stat(self._db)
      if fstat.st_mtime + cache_expire > time.time():
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

  def lookup(self, call: str) -> DXCCRecord:
    return self.get_prefix(call)

  def _get_prefix(self, call: str) -> DXCCRecord:
    call = call.upper()
    prefixes = list({call[:c] for c in range(self._max_len, 0, -1)})
    prefixes.sort(key=lambda x: -len(x))
    with dbm.open(self._db, 'r') as cdb:
      for prefix in prefixes:
        if prefix in cdb:
          return DXCCRecord(**marshal.loads(cdb[prefix]))
    raise KeyError(f"{call} not found")

  def cache_info(self):
    # pylint: disable=no-member
    return self.get_prefix.cache_info()

  def isentity(self, country: str) -> bool:
    if country in self._entities:
      return True
    return False

  @property
  def entities(self) -> DefaultDict[str, set]:
    return self._entities

  def get_entity(self, key: str) -> set:
    if key in self._entities:
      return self._entities[key]
    raise KeyError(f'Entity {key} not found')

  def __str__(self) -> str:
    return f"{self.__class__} {id(self)} ({self._db})"

  def __repr__(self) -> str:
    return str(self)

  @staticmethod
  def load_cty(cty_file: str):
    cty_tmp = cty_file + '.tmp'
    try:
      urlretrieve(CTY_URL, cty_tmp)
      if os.path.exists(cty_file):
        os.unlink(cty_file)
      os.rename(cty_tmp, cty_file)
    except HTTPError as err:
      logging.error(err)
