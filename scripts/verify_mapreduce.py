"""Setup check: does YOUR MongoDB server really execute MapReduce? Run this before anything else.

Uses a throw-away database (`trend_revival_verify`) and deletes it afterwards.
Exit code 0 = MapReduce works. Exit code 1 = it does not (the reason is printed).
"""
import sys

import _bootstrap  # noqa: F401
from bson.code import Code

from config import load_settings
from src.database import check_connection, get_client


def main() -> int:
    settings = load_settings()
    client = get_client(settings)
    ok, info = check_connection(client)
    if not ok:
        print(f"FAIL: cannot connect to MongoDB at {settings.mongodb_uri}\n  {info}\n"
              "  -> Is mongod running? See README section 'Start MongoDB'.")
        return 1
    print(f"Connected. MongoDB server version: {info}")
    import pymongo
    print(f"PyMongo version: {pymongo.version}")
    db = client["trend_revival_verify"]
    try:
        db.drop_collection("t"); db.drop_collection("out")
        db.t.insert_many([{"k": "a"}, {"k": "a"}, {"k": "b"}])
        result = db.command("mapReduce", "t", map=Code("function(){ emit(this.k, 1); }"),
                            reduce=Code("function(k, v){ return Array.sum(v); }"), out={"replace": "out"})
        counts = {d["_id"]: int(d["value"]) for d in db.out.find()}
        if result.get("ok") == 1 and counts == {"a": 2, "b": 1}:
            print(f"PASS: MapReduce executed on the server and returned the correct counts {counts}.")
            return 0
        print(f"FAIL: MapReduce ran but the output was wrong: {counts}")
        return 1
    except Exception as error:  # noqa: BLE001 - we print the exact server error for the user
        print(f"FAIL: the server rejected MapReduce.\n  {type(error).__name__}: {error}\n"
              "  -> Use a MongoDB version that still supports mapReduce (4.2 / 4.4 recommended).")
        return 1
    finally:
        client.drop_database("trend_revival_verify")


if __name__ == "__main__":
    sys.exit(main())
