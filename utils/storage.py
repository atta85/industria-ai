"""
Optional permanent storage in Supabase (free tier), via its REST API, for:
  - analyses: history of signed-in users
  - feedback: tester feedback (signed-in or guest)

It switches on only when SUPABASE_URL and SUPABASE_KEY are in Streamlit
Secrets. The key is the project's secret (service role) key, which stays on
the server; Row Level Security is enabled with no public policies, so the
public key cannot read the tables. Every function fails softly.
"""

import json

import requests

TIMEOUT = 12


class Storage:
    def __init__(self, url: str, key: str):
        self.base = (url or "").rstrip("/") + "/rest/v1"
        self.key = key or ""
        self.enabled = bool(url and key)

    def _headers(self, extra=None):
        h = {"apikey": self.key, "Content-Type": "application/json"}
        if self.key.startswith("eyJ"):            # legacy JWT keys also need the Bearer header
            h["Authorization"] = f"Bearer {self.key}"
        h.update(extra or {})
        return h

    def _post(self, table, row):
        if not self.enabled:
            return False, "Storage is not configured."
        try:
            r = requests.post(f"{self.base}/{table}", headers=self._headers({"Prefer": "return=minimal"}),
                              data=json.dumps(row, default=str), timeout=TIMEOUT)
            if r.status_code in (200, 201, 204):
                return True, ""
            return False, f"Storage error {r.status_code}."
        except requests.exceptions.RequestException:
            return False, "Could not reach the storage service."

    def save_analysis(self, *, user_email, report: dict, problem_label: str):
        rv = report.get("review", {})
        return self._post("analyses", {
            "user_email": (user_email or "").lower(),
            "report_id": report.get("report_id"),
            "industry": report.get("industry"),
            "problem": report.get("problem_statement"),
            "problem_label": problem_label,
            "mode": report.get("mode"),
            "decision": report.get("decision"),
            "summary": rv.get("executive_summary", ""),
            "report": report,
        })

    def list_analyses(self, user_email, limit=25):
        if not self.enabled or not user_email:
            return [], ""
        try:
            r = requests.get(
                f"{self.base}/analyses", headers=self._headers(),
                params={"select": "id,created_at,report_id,industry,problem_label,mode,decision,summary,report",
                        "user_email": f"eq.{user_email.lower()}", "order": "created_at.desc", "limit": str(limit)},
                timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json(), ""
            return [], f"Storage error {r.status_code}."
        except (requests.exceptions.RequestException, ValueError):
            return [], "Could not reach the storage service."

    def save_feedback(self, row: dict):
        return self._post("feedback", row)
