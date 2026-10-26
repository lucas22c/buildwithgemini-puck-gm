import os
from google.cloud import firestore

FIRESTORE_PROJECT = "qwiklabs-gcp-04-ab64a787ffd9"

def seed():
    print(f"Connecting to Firestore in project: {FIRESTORE_PROJECT}")
    db = firestore.Client(project=FIRESTORE_PROJECT)
    players_ref = db.collection("players")

    players = [
        {
            "id": "connor-mcdavid",
            "name": "Connor McDavid",
            "team": "EDM",
            "position": "C",
            "status": "Roster",
            "games_played": 76,
            "goals": 32,
            "assists": 100,
            "points": 132,
            "plus_minus": 35,
            "shots": 263,
            "hits": 112,
            "blocks": 28,
            "fantasy_points_avg": 6.8,
            "injury_status": "Healthy",
            "notes": "Elite multi-category producer and playmaker."
        },
        {
            "id": "nathan-mackinnon",
            "name": "Nathan MacKinnon",
            "team": "COL",
            "position": "C",
            "status": "Roster",
            "games_played": 82,
            "goals": 51,
            "assists": 89,
            "points": 140,
            "plus_minus": 35,
            "shots": 405,
            "hits": 68,
            "blocks": 44,
            "fantasy_points_avg": 7.1,
            "injury_status": "Healthy",
            "notes": "Top tier shot volume and goal scoring engine."
        },
        {
            "id": "cale-makar",
            "name": "Cale Makar",
            "team": "COL",
            "position": "D",
            "status": "Roster",
            "games_played": 77,
            "goals": 21,
            "assists": 69,
            "points": 90,
            "plus_minus": 23,
            "shots": 231,
            "hits": 59,
            "blocks": 148,
            "fantasy_points_avg": 5.9,
            "injury_status": "Healthy",
            "notes": "Premier scoring defenseman with high peripheral blocks."
        },
        {
            "id": "wyatt-johnston",
            "name": "Wyatt Johnston",
            "team": "DAL",
            "position": "C/RW",
            "status": "Waiver",
            "games_played": 82,
            "goals": 32,
            "assists": 33,
            "points": 65,
            "plus_minus": 14,
            "shots": 216,
            "hits": 45,
            "blocks": 49,
            "fantasy_points_avg": 4.1,
            "injury_status": "Healthy",
            "notes": "Emerging breakout forward getting top PP minutes."
        },
        {
            "id": "dakota-joshua",
            "name": "Dakota Joshua",
            "team": "VAN",
            "position": "LW/RW",
            "status": "Waiver",
            "games_played": 63,
            "goals": 18,
            "assists": 14,
            "points": 32,
            "plus_minus": 19,
            "shots": 84,
            "hits": 245,
            "blocks": 38,
            "fantasy_points_avg": 3.7,
            "injury_status": "Healthy",
            "notes": "Banger-league specialist: elite hits and solid scoring touch."
        },
        {
            "id": "connor-hellebuyck",
            "name": "Connor Hellebuyck",
            "team": "WPG",
            "position": "G",
            "status": "Roster",
            "games_played": 60,
            "goals": 0,
            "assists": 2,
            "points": 2,
            "plus_minus": 0,
            "shots": 0,
            "hits": 0,
            "blocks": 0,
            "fantasy_points_avg": 5.4,
            "injury_status": "Healthy",
            "notes": "Vezina caliber starter, high save volume and wins."
        },
        {
            "id": "mats-zuccarello",
            "name": "Mats Zuccarello",
            "team": "MIN",
            "position": "RW",
            "status": "Waiver",
            "games_played": 69,
            "goals": 12,
            "assists": 51,
            "points": 63,
            "plus_minus": -4,
            "shots": 160,
            "hits": 22,
            "blocks": 25,
            "fantasy_points_avg": 3.6,
            "injury_status": "Day-to-Day",
            "notes": "Power play assist specialist, currently day-to-day with lower body injury."
        }
    ]

    for p in players:
        doc_id = p["id"]
        players_ref.document(doc_id).set(p)
        print(f"Seeded player: {p['name']} ({p['team']} - {p['position']}) [{p['status']}]")

    print(f"\nSuccessfully seeded {len(players)} players into collection 'players'!")

if __name__ == "__main__":
    seed()
