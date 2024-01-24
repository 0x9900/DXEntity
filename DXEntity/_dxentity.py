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
import plistlib
import time
import urllib
from collections import defaultdict
from dataclasses import dataclass
from functools import _CacheInfo, _lru_cache_wrapper, lru_cache
from pathlib import Path
from typing import Callable, DefaultDict, Dict

CTY_URL: str = "https://www.country-files.com/cty/cty.plist"
CTY_DB: str = Path.home() / ".local/cty"
CTY_EXPIRE: int = 86400 * 7          # One week

LRU_CACHE_SIZE: int = 2048
TRANSLATOR = ''.maketrans(
  'abcdefghijklmnopqrstuvwxyz',
  'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
  ' !"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'
)


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

  def __init__(self, **kwargs) -> None:
    kwargs = {k.lower(): v for k, v in kwargs.items()}
    for key in DXCCRecord.__slots__:  # pylint: disable=no-member
      setattr(self, key, kwargs[key])


CACHE_TYPE = Callable[[_lru_cache_wrapper], DXCCRecord]
CacheInfo = _CacheInfo


class DXCC:
  # pylint: disable=method-hidden

  def __init__(self, db_path: Path = CTY_DB, cache_size: int = LRU_CACHE_SIZE,
               cache_expire: int = CTY_EXPIRE) -> None:
    if not db_path.parent.exists():
      db_path.parent.mkdir(parents=True)

    self._max_len: int = 0
    self.lookup: CACHE_TYPE = lru_cache(maxsize=cache_size)(self._get_prefix)
    self._db: str = str(db_path)

    try:
      with dbm.open(self._db, 'r') as cdb:
        age = marshal.loads(cdb.get('__age__', 0))
    except dbm.error:
      age = 0
      logging.error('DXEntity cache not found or expired')

    if age + cache_expire > time.time():
      try:
        logging.info('Using DXCC cache %s', self._db)
        with dbm.open(self._db, 'r') as cdb:
          self._max_len = marshal.loads(cdb['__max_len__'])
        return
      except dbm.error as err:
        logging.error('DXEntity cache error: %s', err)

    logging.info('Download %s', CTY_URL)

    with urllib.request.urlopen(CTY_URL) as result:
      raw_data = result.read()
      cty_data = plistlib.loads(raw_data)
    self._max_len = max(len(k) for k in cty_data)

    logging.info('Create cty cache: %s', self._db)
    entities: DefaultDict[str, set] = defaultdict(set)
    with dbm.open(self._db, 'c') as cdb:
      for key, val in cty_data.items():
        cdb[key] = marshal.dumps(val)
        country = val['Country'].translate(TRANSLATOR)
        entities[country].add(key)
      cdb['__age__'] = marshal.dumps(int(time.time()))
      cdb['__max_len__'] = marshal.dumps(self._max_len)
      cdb['__entities__'] = marshal.dumps(dict(entities))

  def _get_prefix(self, call: str) -> DXCCRecord:
    call = call.upper()
    prefixes = list({call[:c] for c in range(self._max_len, 0, -1)})
    prefixes.sort(key=lambda x: -len(x))
    with dbm.open(self._db, 'r') as cdb:
      for prefix in prefixes:
        if prefix in cdb:
          return DXCCRecord(**marshal.loads(cdb[prefix]))
    raise KeyError(f"{call} not found")

  def cache_info(self) -> CacheInfo:
    # pylint: disable=no-member
    return self.lookup.cache_info()  # type: ignore

  def isentity(self, country: str) -> bool:
    country = country.translate(TRANSLATOR)
    if country in self.entities:
      return True
    return False

  @property
  def entities(self) -> Dict[str, set]:
    with dbm.open(self._db, 'r') as cdb:
      return marshal.loads(cdb.get('__entities__'))

  def get_entity(self, key: str) -> set:
    _entities = self.entities
    _key = key.translate(TRANSLATOR)
    if _key in _entities:
      return _entities[_key]
    raise KeyError(f'Entity {key} not found')

  def __str__(self) -> str:
    return f"{self.__class__} {id(self)} ({self._db})"

  def __repr__(self) -> str:
    return str(self)
