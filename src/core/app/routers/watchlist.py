"""
Person watchlist (missing / wanted) is managed directly by the Person Service
at http://localhost:8001/person/watchlist.

This router is kept as a thin shim so the /watchlist prefix still responds
and the frontend can discover the correct target.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


@router.get("")
def watchlist_info():
    return {
        "info": "Person watchlist is managed by the Person Service.",
        "endpoints": {
            "add_person":   "POST   http://localhost:8001/person/watchlist",
            "list_people":  "GET    http://localhost:8001/person/watchlist",
            "remove_person":"DELETE http://localhost:8001/person/watchlist/{category}/{person_id}",
        },
    }
