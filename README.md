# DXEntity

## Amateur Radio Country Files

## Example
```python
In [1]: from DXEntity import DXCC
In [2]: dx = DXCC()
In [3]: dx.lookup('W1AW')
Out[3]: DXCCRecord(country='United States', prefix='K', adif=291, cqzone=5, ituzone=8, continent='NA', latitude=42.38, longitude=71.65, gmtoffset=5.0, exactcallsign=False)
```
