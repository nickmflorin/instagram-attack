## TODO

### Asyncio

- Look into `loop.set_exception_handler(exception_handler)` and
`loop.call_exception_handler`


### Proxies

#### Prioritization Notes

We should be looking at prioritizing proxies by `confirmed = True` where
the time since it was last used is above a threshold (if it caused a too
many requests error) and then look at metrics.

```python
import heapq

data = [
    ((5, 1, 2), 'proxy1'),
    ((5, 2, 1), 'proxy2'),
    ((3, 1, 2), 'proxy3'),
    ((5, 1, 1), 'proxy5'),
]

heapq.heapify(data)
for item in data:
    print(item)
```

We will have to re-heapify whenever we go to get a proxy (hopefully not
too much processing) - if it is, we should limit the size of the proxy queue.

Priority can be something like (x), (max_resp_time), (error_rate), (times used)
x is determined if confirmed AND time since last used > x (binary)
y is determined if not confirmed and time since last used > x (binary)

Then we will always have prioritized by confirmed and available, not confirmed
but ready, all those not used yet... Might not need to prioritize by times
not used since that is guaranteed (at least should be) 0 after the first
two priorities
