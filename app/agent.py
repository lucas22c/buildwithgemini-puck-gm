# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from typing import Any, Dict, List, Optional
from google.cloud import firestore

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types


MODEL = "gemini-3.8-flash"
FIRESTORE_PROJECT = "qwiklabs-gcp-04-ab64a787ffd9"


def get_firestore_client() -> firestore.Client:
    """Return a Firestore client configured with explicit project ID."""
    return firestore.Client(project=FIRESTORE_PROJECT)


def list_players(status: Optional[str] = None, position: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists players from Firestore with optional filtering by roster status or position.

    Args:
        status: Optional filter by status ('Roster', 'Waiver', 'Watchlist').
        position: Optional filter by position ('C', 'LW', 'RW', 'D', 'G').

    Returns:
        A list of player records matching the criteria.
    """
    db = get_firestore_client()
    query = db.collection("players")
    if status:
        query = query.where("status", "==", status)
    
    docs = query.stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        if position:
            pos_val = data.get("position", "")
            if position.upper() not in pos_val.upper():
                continue
        results.append(data)
    return results


def get_player(player_name: str) -> Dict[str, Any]:
    """Retrieves full details and stats for a specific player by name.

    Args:
        player_name: The name or part of the name of the player to look up.

    Returns:
        The player dictionary if found, or an error message.
    """
    db = get_firestore_client()
    docs = db.collection("players").stream()
    matched = []
    target = player_name.strip().lower()
    for doc in docs:
        data = doc.to_dict()
        if target in data.get("name", "").lower():
            matched.append(data)

    if not matched:
        return {"error": f"No player found matching '{player_name}'."}
    return matched[0] if len(matched) == 1 else {"matched_players": matched}


def update_player_status(player_name: str, new_status: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """Updates a player's fantasy status (e.g. 'Roster', 'Waiver', 'Watchlist', 'Bench') and optional notes.
    When a player is placed on the Watchlist or interest is shown, this change is saved to Firestore
    and preserved in the manager's long-term memory.

    Args:
        player_name: The name of the player to update.
        new_status: The new status ('Roster', 'Waiver', 'Watchlist', 'Bench').
        notes: Optional updated scouting note, reason for interest, or tracking criteria.

    Returns:
        Confirmation of update with the updated player data.
    """
    db = get_firestore_client()
    docs = list(db.collection("players").stream())
    target = player_name.strip().lower()
    match_doc = None
    for doc in docs:
        if target in doc.to_dict().get("name", "").lower():
            match_doc = doc
            break

    if not match_doc:
        return {"error": f"Player '{player_name}' not found."}

    update_fields: Dict[str, Any] = {"status": new_status}
    if notes:
        update_fields["notes"] = notes

    db.collection("players").document(match_doc.id).update(update_fields)
    updated_data = db.collection("players").document(match_doc.id).get().to_dict()
    return {
        "message": f"Successfully updated {updated_data.get('name')} to {new_status} (watchlist/roster tracking active).",
        "player": updated_data
    }


def add_player(
    name: str,
    team: str,
    position: str,
    status: str = "Waiver",
    goals: int = 0,
    assists: int = 0,
    points: int = 0,
    hits: int = 0,
    blocks: int = 0,
    fantasy_points_avg: float = 0.0,
    injury_status: str = "Healthy",
    notes: str = ""
) -> Dict[str, Any]:
    """Adds a new player to the fantasy database.

    Args:
        name: Full player name.
        team: NHL 3-letter team abbreviation (e.g. EDM, TOR, NYR).
        position: Player position ('C', 'LW', 'RW', 'D', 'G').
        status: Fantasy status ('Roster', 'Waiver', 'Watchlist'). Default 'Waiver'.
        goals: Season goals scored.
        assists: Season assists.
        points: Season total points.
        hits: Season hits.
        blocks: Season blocked shots.
        fantasy_points_avg: Average fantasy points per game.
        injury_status: Current injury status ('Healthy', 'Day-to-Day', 'IR').
        notes: Scouting notes or player summary.

    Returns:
        Confirmation message and newly created player record.
    """
    db = get_firestore_client()
    doc_id = name.strip().lower().replace(" ", "-")
    player_data = {
        "id": doc_id,
        "name": name,
        "team": team.upper(),
        "position": position.upper(),
        "status": status,
        "games_played": 0,
        "goals": goals,
        "assists": assists,
        "points": points,
        "plus_minus": 0,
        "shots": 0,
        "hits": hits,
        "blocks": blocks,
        "fantasy_points_avg": fantasy_points_avg,
        "injury_status": injury_status,
        "notes": notes
    }
    db.collection("players").document(doc_id).set(player_data)
    return {"message": f"Added player {name} ({team}) to database.", "player": player_data}


def get_team_schedule(team_abbr: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetches upcoming or recent NHL games for a team from the official NHL schedule API.

    Args:
        team_abbr: 3-letter NHL team abbreviation (e.g. 'EDM', 'COL', 'TOR', 'VAN', 'DAL', 'NYR').
        limit: Number of games to return (default 5).

    Returns:
        A list of game summaries with date, opponent, and home/away status.
    """
    import json
    import urllib.request
    from datetime import date

    team = team_abbr.strip().upper()
    url = f"https://api-web.nhle.com/v1/club-schedule-season/{team}/now"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            all_games = data.get("games", [])

            today_str = date.today().isoformat()
            # Filter for upcoming games, or fallback to the latest games if season hasn't reached date
            upcoming = [g for g in all_games if g.get("gameDate", "") >= today_str]
            selected = upcoming[:limit] if upcoming else all_games[-limit:]

            results = []
            for g in selected:
                home = g.get("homeTeam", {}).get("abbrev", "")
                away = g.get("awayTeam", {}).get("abbrev", "")
                is_home = (home == team)
                opponent = away if is_home else home
                results.append({
                    "game_date": g.get("gameDate"),
                    "team": team,
                    "opponent": opponent,
                    "location": "Home" if is_home else "Away",
                    "game_type": g.get("gameType")
                })
            return results
    except Exception as e:
        return [{"error": f"Failed to fetch schedule for {team}: {str(e)}"}]


def get_team_standings(team_abbr: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches real NHL standings, record (wins, losses, OT losses, points), and goal differentials.

    Args:
        team_abbr: Optional 3-letter NHL team abbreviation (e.g. 'EDM', 'COL', 'NYR', 'TOR') to get standings for a specific team. If omitted, returns the top 10 league teams.

    Returns:
        List of team standing records with current points, record, streak, and goal differential.
    """
    import json
    import urllib.request

    url = "https://api-web.nhle.com/v1/standings/now"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            standings = data.get("standings", [])
            
            results = []
            target = team_abbr.strip().upper() if team_abbr else None

            for s in standings:
                abbrev = s.get("teamAbbrev", {}).get("default", "")
                team_name = s.get("teamName", {}).get("default", abbrev)
                if target and abbrev != target:
                    continue

                results.append({
                    "team": abbrev,
                    "team_name": team_name,
                    "games_played": s.get("gamesPlayed", 0),
                    "wins": s.get("wins", 0),
                    "losses": s.get("losses", 0),
                    "ot_losses": s.get("otLosses", 0),
                    "points": s.get("points", 0),
                    "point_pctg": round(s.get("pointPctg", 0.0), 3),
                    "goal_differential": s.get("goalDifferential", 0),
                    "streak_code": s.get("streakCode", ""),
                    "division": s.get("divisionName", ""),
                    "conference": s.get("conferenceName", ""),
                })
                if target:
                    break

            return results if target else results[:10]
    except Exception as e:
        return [{"error": f"Failed to fetch NHL standings: {str(e)}"}]


GCS_BUCKET_NAME = "puck-gm-media-ab64a7"


def generate_hockey_image(
    prompt: str,
    filename_prefix: str = "warroom_card",
    tool_context: Optional[Any] = None
) -> Dict[str, Any]:
    """Generates a fantasy hockey image (team logo, rivalry hype poster, or player spotlight badge).

    Uses gemini-3.1-flash-lite-image in the global location. Saves the generated image as an
    ADK artifact (so it appears in the Playground Artifacts panel) and uploads the bytes to
    the public Cloud Storage bucket, returning the public HTTPS URL.

    Args:
        prompt: Visual description for the image (e.g. 'Vintage hockey goalie mask logo on ice').
        filename_prefix: Optional prefix for filename (e.g. 'oilers_hype', 'connor_badge').
        tool_context: Injected ToolContext provided by ADK.

    Returns:
        Dictionary containing public_url, artifact_saved, and prompt details.
    """
    import uuid
    from google import genai
    from google.cloud import storage

    unique_id = uuid.uuid4().hex[:8]
    clean_prefix = filename_prefix.strip().lower().replace(" ", "_")
    image_filename = f"{clean_prefix}_{unique_id}.jpg"

    # 1. Generate image using gemini-3.1-flash-lite-image in global location
    ai_client = genai.Client(
        vertexai=True,
        project=FIRESTORE_PROJECT,
        location="global"
    )
    response = ai_client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt
    )

    image_bytes = None
    mime_type = "image/jpeg"
    for cand in response.candidates:
        for part in cand.content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                mime_type = part.inline_data.mime_type or "image/jpeg"
                break
        if image_bytes:
            break

    if not image_bytes:
        return {"error": "Failed to generate image bytes from model."}

    # 2. Save artifact to ADK tool_context (shows in Playground Artifacts panel)
    artifact_saved = False
    if tool_context and hasattr(tool_context, "save_artifact"):
        try:
            artifact_part = types.Part(
                inline_data=types.Blob(
                    data=image_bytes,
                    mime_type=mime_type
                )
            )
            tool_context.save_artifact(
                filename=image_filename,
                artifact=artifact_part,
                custom_metadata={"prompt": prompt, "model": "gemini-3.1-flash-lite-image"}
            )
            artifact_saved = True
        except Exception as e:
            print(f"Warning: tool_context.save_artifact failed: {e}")

    # 3. Upload bytes to public Cloud Storage bucket without writing to local file
    storage_client = storage.Client(project=FIRESTORE_PROJECT)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(image_filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{image_filename}"

    return {
        "status": "success",
        "public_url": public_url,
        "artifact_saved": artifact_saved,
        "filename": image_filename,
        "prompt": prompt
    }


def generate_hockey_video(
    prompt: str,
    item_type: str = "highlight",
    duration_seconds: int = 3,
    tool_context: Optional[Any] = None
) -> Dict[str, Any]:
    """Generates a short hockey video (highlight, goal celebration, rivalry teaser, player motion,
    or hype clip) using Google's Omni model (gemini-omni-flash-preview) in the global region.
    Saves the video as an artifact so it appears in the Playground's Artifacts panel, uploads
    the bytes directly to the public Cloud Storage bucket, and returns its public HTTPS URL.
    Does NOT write the video to a local file.

    Args:
        prompt: Detailed visual prompt describing the hockey video (action, lighting, angle, player).
        item_type: Type of item/clip (e.g. 'highlight', 'celebration', 'slapshot', 'hypetrailer').
        duration_seconds: Duration between 3 and 10 seconds (default: 3).
        tool_context: ADK ToolContext injected automatically by the runtime.
    """
    import urllib.request
    import json
    import time
    import re
    from google.auth import default
    from google.auth.transport.requests import Request
    from google.cloud import storage

    duration = max(3, min(int(duration_seconds), 10))
    duration_str = f"{duration}s"

    timestamp = int(time.time())
    safe_slug = re.sub(r"[^a-zA-Z0-9]+", "_", item_type).strip("_").lower() or "clip"
    video_filename = f"puckgm_omni_{safe_slug}_{timestamp}.mp4"

    # Authenticate to Vertex AI Interactions API
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    token = credentials.token

    url = f"https://aiplatform.googleapis.com/v1beta1/projects/{FIRESTORE_PROJECT}/locations/global/interactions"

    # Prefix temporary output folder in public GCS bucket
    temp_prefix = f"omni_temp_{timestamp}/"
    gcs_output_uri = f"gs://{GCS_BUCKET_NAME}/{temp_prefix}"

    payload = {
        "model": "gemini-omni-flash-preview",
        "input": [
            {"type": "text", "text": prompt}
        ],
        "response_format": [
            {
                "type": "video",
                "delivery": "uri",
                "gcs_uri": gcs_output_uri,
                "aspect_ratio": "16:9",
                "resolution": "720p",
                "duration": duration_str
            }
        ],
        "generation_config": {
            "video_config": {
                "task": "text_to_video"
            }
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            api_resp = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        error_msg = str(e)
        if hasattr(e, "read"):
            try:
                error_msg = e.read().decode("utf-8")
            except Exception:
                pass
        return {"error": f"Omni video generation failed: {error_msg}"}

    # Extract output GCS URI from interaction steps
    generated_uri = None
    for step in api_resp.get("steps", []):
        if step.get("type") == "model_output":
            for item in step.get("content", []):
                if item.get("type") == "video" and item.get("uri"):
                    generated_uri = item.get("uri")
                    break
        if generated_uri:
            break

    if not generated_uri:
        return {"error": "No generated video URI returned by gemini-omni-flash-preview."}

    # Read generated video bytes directly into memory from GCS
    storage_client = storage.Client(project=FIRESTORE_PROJECT)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)

    # generated_uri format: gs://<bucket>/<blob_name>
    blob_name = generated_uri.replace(f"gs://{GCS_BUCKET_NAME}/", "")
    temp_blob = bucket.blob(blob_name)
    video_bytes = temp_blob.download_as_bytes()

    mime_type = "video/mp4"

    # (1) Save with tool_context.save_artifact so it shows up in Playground's Artifacts panel
    artifact_saved = False
    if tool_context and hasattr(tool_context, "save_artifact"):
        try:
            artifact_part = types.Part(
                inline_data=types.Blob(
                    data=video_bytes,
                    mime_type=mime_type
                )
            )
            tool_context.save_artifact(
                filename=video_filename,
                artifact=artifact_part,
                custom_metadata={
                    "prompt": prompt,
                    "model": "gemini-omni-flash-preview",
                    "region": "global",
                    "duration": duration_str
                }
            )
            artifact_saved = True
        except Exception as e:
            print(f"Warning: tool_context.save_artifact failed: {e}")

    # (2) Upload the same video bytes to the public Cloud Storage bucket and return public HTTPS URL
    dest_blob = bucket.blob(video_filename)
    dest_blob.upload_from_string(video_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{video_filename}"

    # Clean up temporary generation blob
    try:
        temp_blob.delete()
    except Exception:
        pass

    return {
        "status": "success",
        "public_url": public_url,
        "artifact_saved": artifact_saved,
        "filename": video_filename,
        "prompt": prompt,
        "duration": duration_str,
        "model": "gemini-omni-flash-preview",
        "region": "global"
    }


def fetch_and_save_player_profile_picture(
    player_name: str,
    team_abbr: Optional[str] = None,
    tool_context: Optional[Any] = None
) -> Dict[str, Any]:
    """Fetches an official player profile picture/headshot from the public NHL roster API,
    uploads it to the public Google Cloud Storage bucket, and attaches the public image URL
    to the player's profile in Firestore.

    Args:
        player_name: Full name of the player (e.g. 'Connor McDavid', 'Cale Makar', 'Dakota Joshua').
        team_abbr: Optional 3-letter NHL team abbreviation (e.g. 'EDM', 'COL', 'VAN'). If omitted,
                   the player's team is looked up from Firestore or scanned across NHL rosters.
        tool_context: Injected ToolContext provided by ADK.

    Returns:
        Dictionary with status, player_name, headshot_source_url, gcs_image_url, and firestore_updated status.
    """
    import json
    import urllib.request
    from google.cloud import storage

    # 1. Lookup player in Firestore to get their current team or record
    db = get_firestore_client()
    docs = list(db.collection("players").stream())
    target = player_name.strip().lower()
    match_doc = None
    for doc in docs:
        if target in doc.to_dict().get("name", "").lower():
            match_doc = doc
            break

    matched_data = match_doc.to_dict() if match_doc else {}
    actual_name = matched_data.get("name", player_name)
    primary_team = (team_abbr or matched_data.get("team", "")).strip().upper()

    # Determine teams to search: start with primary team if known, then common contenders
    teams_to_search = []
    if primary_team:
        teams_to_search.append(primary_team)

    # 2. Query the official NHL roster API
    headshot_url = None
    matched_nhl_player = None

    def search_roster_for_player(team: str, query: str):
        for endpoint in (f"https://api-web.nhle.com/v1/roster/{team}/current", f"https://api-web.nhle.com/v1/roster/{team}/20232024"):
            req = urllib.request.Request(endpoint, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    for group in ("forwards", "defensemen", "goalies"):
                        for p in data.get(group, []):
                            first = p.get("firstName", {}).get("default", "")
                            last = p.get("lastName", {}).get("default", "")
                            full = f"{first} {last}".strip()
                            if query.lower() in full.lower() or query.lower() in last.lower():
                                return p
            except Exception:
                continue
        return None

    # Try primary team first
    if primary_team:
        matched_nhl_player = search_roster_for_player(primary_team, actual_name)

    # If not found yet, get all active teams from NHL standings to find their current team
    if not matched_nhl_player:
        candidates = ["EDM", "COL", "WPG", "VAN", "DAL", "MIN", "OTT", "TOR", "NYR", "BOS", "VGK", "CAR", "FLA"]
        for tm in candidates:
            if tm == primary_team:
                continue
            matched_nhl_player = search_roster_for_player(tm, actual_name)
            if matched_nhl_player:
                primary_team = tm
                break

    if not matched_nhl_player or not matched_nhl_player.get("headshot"):
        return {"error": f"Could not find an official NHL headshot for player '{actual_name}' on current rosters."}

    headshot_url = matched_nhl_player["headshot"]
    nhl_id = matched_nhl_player.get("id", "headshot")

    # 3. Download the official headshot bytes from the NHL CDN
    img_req = urllib.request.Request(headshot_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(img_req, timeout=8) as img_resp:
            image_bytes = img_resp.read()
            mime_type = img_resp.headers.get("Content-Type", "image/png")
    except Exception as e:
        return {"error": f"Failed to download headshot image from NHL API: {e}"}

    # 4. Save to ADK tool_context artifact (shows in Playground Artifacts tab)
    safe_name = actual_name.strip().lower().replace(" ", "_")
    image_filename = f"headshot_{safe_name}_{nhl_id}.png"
    artifact_saved = False
    if tool_context and hasattr(tool_context, "save_artifact"):
        try:
            artifact_part = types.Part(
                inline_data=types.Blob(
                    data=image_bytes,
                    mime_type=mime_type
                )
            )
            tool_context.save_artifact(
                filename=image_filename,
                artifact=artifact_part,
                custom_metadata={"player": actual_name, "team": primary_team, "source": "nhl_roster_api"}
            )
            artifact_saved = True
        except Exception as e:
            print(f"Warning: tool_context.save_artifact failed: {e}")

    # 5. Upload bytes directly to Google Cloud Storage bucket
    storage_client = storage.Client(project=FIRESTORE_PROJECT)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(image_filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    gcs_public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{image_filename}"

    # 6. Attach image_url to the player document in Firestore
    firestore_updated = False
    if match_doc:
        db.collection("players").document(match_doc.id).update({
            "image_url": gcs_public_url,
            "profile_picture": gcs_public_url,
            "nhl_headshot_url": headshot_url,
            "team": primary_team or match_doc.to_dict().get("team")
        })
        firestore_updated = True

    return {
        "status": "success",
        "player_name": actual_name,
        "team": primary_team,
        "nhl_headshot_source": headshot_url,
        "image_url": gcs_public_url,
        "firestore_updated": firestore_updated,
        "artifact_saved": artifact_saved,
        "filename": image_filename,
        "message": f"Successfully pulled official NHL roster headshot for {actual_name}, stored in Google Cloud Storage ({gcs_public_url}), and attached to player record in Firestore."
    }


def get_player_momentum_stats(nhl_id: int) -> Dict[str, Any]:
    """Fetches real-time player landing data from NHL API, extracting recent 5-game momentum,
    power play production, and shooting percentage."""
    import json
    import urllib.request

    url = f"https://api-web.nhle.com/v1/player/{nhl_id}/landing"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            l5 = data.get("last5Games", [])
            sub = data.get("featuredStats", {}).get("regularSeason", {}).get("subSeason", {})

            # For skaters:
            l5_pts = sum(g.get("points", 0) for g in l5)
            l5_goals = sum(g.get("goals", 0) for g in l5)
            l5_assists = sum(g.get("assists", 0) for g in l5)
            l5_shots = sum(g.get("shots", 0) for g in l5)

            # Trend momentum rating:
            if l5_pts >= 8:
                trend = "Blazing Hot 🔥"
            elif l5_pts >= 5:
                trend = "Surging Up 📈"
            elif l5_pts <= 2 and len(l5) == 5:
                trend = "Cold Slump ❄️"
            else:
                trend = "Steady Average ⚖️"

            return {
                "nhl_id": nhl_id,
                "current_season_ppp": sub.get("powerPlayPoints", 0),
                "current_season_ppg": sub.get("powerPlayGoals", 0),
                "current_season_shooting_pctg": round(sub.get("shootingPctg", 0.0) * 100, 1),
                "last_5_games": {
                    "games_sampled": len(l5),
                    "goals": l5_goals,
                    "assists": l5_assists,
                    "points": l5_pts,
                    "shots": l5_shots,
                    "trend": trend
                }
            }
    except Exception as e:
        return {"nhl_id": nhl_id, "error": str(e), "last_5_games": {"trend": "Data Unavailable"}}


def analyze_trade(
    giving_players: List[str],
    receiving_players: List[str],
    scoring_mode: str = "banger_points"
) -> Dict[str, Any]:
    """Analyzes a proposed fantasy hockey trade between two managers or sides.
    Powered by the official NHL Player Landing API to evaluate recent 5-game momentum,
    power play production, total scoring, peripheral stats (hits, blocks), and projected fantasy points.

    Args:
        giving_players: List of player names being traded away (e.g. ['Nathan MacKinnon']).
        receiving_players: List of player names being acquired (e.g. ['Brady Tkachuk', 'Wyatt Johnston']).
        scoring_mode: League scoring format ('banger_points', 'standard_points', 'category_h2h').

    Returns:
        Structured breakdown with stats comparison, recent momentum analysis, net difference, verdict ('Win', 'Loss', 'Fair'), and strategic advice.
    """
    import re
    db = get_firestore_client()
    docs = list(db.collection("players").stream())
    all_players = {d.to_dict().get("name", "").lower(): d.to_dict() for d in docs}

    def resolve_side(names: List[str]):
        side_players = []
        missing = []
        for n in names:
            target = n.strip().lower()
            found = None
            for p_name, p_data in all_players.items():
                if target in p_name:
                    found = p_data
                    break
            if found:
                # Extract NHL ID if present in player profile or image URL
                nhl_id = found.get("nhl_id")
                if not nhl_id:
                    # Parse from headshot url e.g. ..._8478402.png
                    match = re.search(r"(\d{7,8})", found.get("image_url", "") + found.get("nhl_headshot_url", ""))
                    if match:
                        nhl_id = int(match.group(1))

                # Enrich with Player Landing & Momentum API
                momentum = get_player_momentum_stats(nhl_id) if nhl_id else {"last_5_games": {"trend": "N/A"}}
                enriched = dict(found)
                enriched["momentum"] = momentum
                side_players.append(enriched)
            else:
                missing.append(n)
        return side_players, missing

    side_give, missing_give = resolve_side(giving_players)
    side_recv, missing_recv = resolve_side(receiving_players)

    if missing_give or missing_recv:
        missing_all = missing_give + missing_recv
        return {
            "error": f"The following players could not be found in the database: {', '.join(missing_all)}. Please add or verify their names."
        }

    def aggregate_stats(players: List[Dict[str, Any]]):
        l5_pts_total = sum(p.get("momentum", {}).get("last_5_games", {}).get("points", 0) for p in players)
        l5_goals_total = sum(p.get("momentum", {}).get("last_5_games", {}).get("goals", 0) for p in players)
        l5_shots_total = sum(p.get("momentum", {}).get("last_5_games", {}).get("shots", 0) for p in players)
        ppp_total = sum(p.get("momentum", {}).get("current_season_ppp", 0) for p in players)

        player_summaries = []
        for p in players:
            m = p.get("momentum", {}).get("last_5_games", {})
            player_summaries.append({
                "name": p.get("name"),
                "trend": m.get("trend", "Steady"),
                "last_5_pts": m.get("points", 0),
                "power_play_pts": p.get("momentum", {}).get("current_season_ppp", 0),
                "season_fpts_avg": p.get("fantasy_points_avg", 0.0),
                "injury_status": p.get("injury_status", "Healthy")
            })

        return {
            "player_count": len(players),
            "players": [p.get("name") for p in players],
            "player_momentum_breakdown": player_summaries,
            "total_goals": sum(p.get("goals", 0) for p in players),
            "total_assists": sum(p.get("assists", 0) for p in players),
            "total_points": sum(p.get("points", 0) for p in players),
            "total_hits": sum(p.get("hits", 0) for p in players),
            "total_blocks": sum(p.get("blocks", 0) for p in players),
            "total_shots": sum(p.get("shots", 0) for p in players),
            "total_fpts_avg": round(sum(p.get("fantasy_points_avg", 0.0) for p in players), 2),
            "recent_momentum_l5_pts": l5_pts_total,
            "recent_momentum_l5_goals": l5_goals_total,
            "recent_momentum_l5_shots": l5_shots_total,
            "total_power_play_pts": ppp_total,
            "injuries": [f"{p.get('name')} ({p.get('injury_status')})" for p in players if p.get("injury_status", "Healthy") != "Healthy"]
        }

    give_totals = aggregate_stats(side_give)
    recv_totals = aggregate_stats(side_recv)

    net_fpts = round(recv_totals["total_fpts_avg"] - give_totals["total_fpts_avg"], 2)
    net_points = recv_totals["total_points"] - give_totals["total_points"]
    net_hits = recv_totals["total_hits"] - give_totals["total_hits"]
    net_blocks = recv_totals["total_blocks"] - give_totals["total_blocks"]
    net_l5_pts = recv_totals["recent_momentum_l5_pts"] - give_totals["recent_momentum_l5_pts"]
    net_ppp = recv_totals["total_power_play_pts"] - give_totals["total_power_play_pts"]

    # Evaluate trade verdict
    if net_fpts >= 1.5 or (net_fpts >= 0.5 and net_l5_pts >= 3):
        verdict = "Strong Win 🔥"
        recommendation = "Accept immediately. Significant fantasy output boost and positive player momentum."
    elif net_fpts >= 0.3 or (net_fpts >= 0.0 and net_l5_pts >= 2):
        verdict = "Slight Win 📈"
        recommendation = "Favorable deal. You gain an advantage in projected fantasy points and recent form."
    elif net_fpts >= -0.5:
        if net_hits > 50 or net_blocks > 30:
            verdict = "Fair / Category Specialist Win 🛡️"
            recommendation = "Balanced points trade with massive upside in peripheral banger categories (hits/blocks)."
        else:
            verdict = "Even / Fair Trade ⚖️"
            recommendation = "Fair exchange with balanced value on both sides."
    else:
        verdict = "Trade Loss ❌"
        recommendation = "Decline or counteroffer. You are giving up higher overall fantasy value than you receive."

    return {
        "status": "success",
        "scoring_mode": scoring_mode,
        "giving_side": give_totals,
        "receiving_side": recv_totals,
        "net_differential": {
            "net_fantasy_points_avg": net_fpts,
            "net_recent_l5_points_momentum": net_l5_pts,
            "net_power_play_points": net_ppp,
            "net_points": net_points,
            "net_hits": net_hits,
            "net_blocks": net_blocks,
        },
        "verdict": verdict,
        "recommendation": recommendation,
        "injury_risks": recv_totals["injuries"] or "None on receiving side."
    }


from google.adk.agents.callback_context import CallbackContext
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.tools.preload_memory_tool import PreloadMemoryTool

SANDBOX_RESOURCE_NAME = "projects/1705963223/locations/us-east1/reasoningEngines/1340549865351938048/sandboxEnvironments/8343925462354886656"

sandbox_executor = AgentEngineSandboxCodeExecutor(
    sandbox_resource_name=SANDBOX_RESOURCE_NAME
)


async def generate_memories_callback(callback_context: CallbackContext):
    """After each turn, send session events to Memory Bank for extraction."""
    await callback_context.add_session_to_memory()
    return None


try:
    from app.a2ui_instruction_cache import A2UI_INSTRUCTION as a2ui_instruction
except ImportError:
    from a2ui.basic_catalog.provider import BasicCatalog
    from a2ui.schema.manager import A2uiSchemaManager

    schema_manager = A2uiSchemaManager(
        version="0.8",
        catalogs=[BasicCatalog.get_config("0.8")],
    )

    a2ui_instruction = schema_manager.generate_system_prompt(
        role_description=(
            "You are PuckGM, an expert Fantasy Hockey Assistant General Manager in the War Room. "
            "You help fantasy managers track their roster, scout waiver wire targets, analyze player stats "
            "(goals, assists, hits, blocks, fantasy points average), manage injury situations, execute "
            "roster moves (adding players, moving players between Roster, Waiver, and Watchlist), evaluate "
            "team momentum using live NHL standings, check real NHL schedules for matchup planning, "
            "generate custom team logos and graphics, and safely run Python code calculations in a secure "
            "Agent Engine sandbox for complex fantasy analytics (e.g. projecting weekly points, calculating "
            "Z-scores or weighted standard deviations for category league values). "
            "Actively track and remember all players the manager expresses interest in or places on their Watchlist across conversations."
        ),
        workflow_description="Analyze the user request, call Firestore/NHL/image/sandbox tools as needed, and return structured A2UI cards when presenting players, rosters, schedules, standings, analytics, or team graphics.",
        ui_description=(
            "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
            "Never nest a Card inside a Card. "
            "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
            "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
            "nothing in adk web). "
            "You may include one Image component, but only when you have a public https "
            "URL for the image (for example the URL an image tool returns after uploading "
            "to a public bucket). Set the Image url to that exact https link, for example "
            "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
            "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
            "not have a public URL, add a short Text line noting the image instead. "
            "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
            "headings and emphasis. "
            "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
            "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
        ),
        include_schema=True,
        include_examples=True,
    )

from app.a2ui_utils import a2ui_callback


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    code_executor=sandbox_executor,
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
    tools=[
        PreloadMemoryTool(),
        list_players,
        get_player,
        update_player_status,
        add_player,
        get_team_schedule,
        get_team_standings,
        generate_hockey_image,
        generate_hockey_video,
        fetch_and_save_player_profile_picture,
        analyze_trade,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
