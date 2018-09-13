from pymongo import *
from datetime import *


def StatsBeginXfr(info):
    with MongoClient("mongodb://owner:Li950109@eg-mongodb.bucknell.edu/yl015") as client:
        db = client["yl015"]
        col = db["xTP"]

        oid = col.insert({
            "Created": datetime.utcnow(),
            **{k:info[k] for k in ['filename', 'total_frags', 'total_size', 'offset']},
            "events": []
        })
        return oid
def StatsLookup(oid):
    with MongoClient("mongodb://owner:Li950109@eg-mongodb.bucknell.edu/yl015") as client:
        db = client["yl015"]
        col = db["xTP"]
        return col.find_one({"_id": oid})
def StatsUpdate(info, xtype, message, value):
    with MongoClient("mongodb://owner:Li950109@eg-mongodb.bucknell.edu/yl015") as client:
        db = client["yl015"]
        col = db["xTP"]
        col.update(
            {"_id": info['oid']},
            {"$push":
                {"events":
                    {
                        "when": datetime.utcnow(),
                        "type": xtype,
                        "message": message,
                        "value": value
                    }
                }
            }
        )

if __name__=="__main__":

    oid = StatsBeginXfr({
        'filename': 'testme',
        'total_frags': 1,
        'total_size': 222,
        'offset': 0
    })
    print(oid)

    print(StatsLookup(oid))
    StatsUpdate({'oid':oid}, 4, "hiya", True)
