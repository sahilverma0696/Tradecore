from enum import Enum

class ORDERSTATE(Enum):
    OPEN = 1,
    CLOSE = 2,
    ARCHIVED = 3
    
    
class ORDERSIDE(Enum):
    BUY = 1,
    SELL = 2,