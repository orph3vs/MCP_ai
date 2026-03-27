from __future__ import annotations

import json
from typing import Any, Dict, Optional

from src.models import ResolvedLaw


PRIVACY_LAW = ResolvedLaw("011357", "개인정보 보호법", "https://www.law.go.kr/법령/개인정보보호법")
NETWORK_LAW = ResolvedLaw(
    "000030",
    "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
    "https://www.law.go.kr/법령/정보통신망이용촉진및정보보호등에관한법률",
)
ECOM_LAW = ResolvedLaw(
    "000111",
    "전자상거래 등에서의 소비자보호에 관한 법률",
    "https://www.law.go.kr/법령/전자상거래등에서의소비자보호에관한법률",
)


class FakeLawGateway:
    def __init__(self) -> None:
        self.laws = {
            PRIVACY_LAW.law_name: PRIVACY_LAW,
            NETWORK_LAW.law_name: NETWORK_LAW,
            ECOM_LAW.law_name: ECOM_LAW,
        }
        self.articles = {
            (PRIVACY_LAW.law_id, "제15조"): "제15조(개인정보의 수집ㆍ이용) 개인정보처리자는 다음 각 호의 어느 하나에 해당하는 경우 개인정보를 수집할 수 있다.",
            (PRIVACY_LAW.law_id, "제17조"): "제17조(개인정보의 제공) 개인정보처리자는 정보주체의 동의를 받거나 법률에 특별한 규정이 있는 경우에 개인정보를 제3자에게 제공할 수 있다.",
            (PRIVACY_LAW.law_id, "제18조"): "제18조(개인정보의 목적 외 이용ㆍ제공 제한) 개인정보처리자는 목적 외 이용 또는 제공을 하여서는 아니 된다.",
            (PRIVACY_LAW.law_id, "제20조"): "제20조(정보주체 이외로부터 수집한 개인정보의 수집 출처 등 고지) 개인정보처리자는 수집 출처 등을 알려야 한다.",
            (PRIVACY_LAW.law_id, "제21조"): "제21조(개인정보의 파기) 개인정보처리자는 보유기간이 경과한 개인정보를 지체 없이 파기하여야 한다.",
            (PRIVACY_LAW.law_id, "제23조"): "제23조(민감정보의 처리 제한) 개인정보처리자는 민감정보를 처리하여서는 아니 된다.",
            (PRIVACY_LAW.law_id, "제24조"): "제24조(고유식별정보의 처리 제한) 개인정보처리자는 고유식별정보를 처리할 수 있는 경우를 제한한다.",
            (PRIVACY_LAW.law_id, "제24조의2"): "제24조의2(주민등록번호 처리의 제한) 주민등록번호는 법령상 근거가 있는 경우 등에만 처리할 수 있다.",
            (PRIVACY_LAW.law_id, "제25조"): "제25조(고정형 영상정보처리기기의 설치ㆍ운영 제한) 공개된 장소에 고정형 영상정보처리기기를 설치ㆍ운영할 수 있는 경우를 정한다.",
            (PRIVACY_LAW.law_id, "제26조"): "제26조(업무위탁에 따른 개인정보의 처리 제한) 개인정보처리자는 업무를 위탁할 수 있다.",
            (PRIVACY_LAW.law_id, "제29조"): "제29조(안전조치의무) 개인정보처리자는 안전성 확보에 필요한 기술적ㆍ관리적 및 물리적 조치를 하여야 한다.",
            (PRIVACY_LAW.law_id, "제34조"): "제34조(개인정보 유출 등의 통지ㆍ신고) 개인정보처리자는 개인정보 유출 등을 알게 되었을 때에는 통지 또는 신고하여야 한다.",
            (PRIVACY_LAW.law_id, "제35조"): "제35조(개인정보의 열람) 정보주체는 자신의 개인정보에 대한 열람을 요구할 수 있다.",
            (PRIVACY_LAW.law_id, "제36조"): "제36조(개인정보의 정정ㆍ삭제) 정보주체는 자신의 개인정보의 정정 또는 삭제를 요구할 수 있다.",
            (PRIVACY_LAW.law_id, "제37조"): "제37조(개인정보의 처리정지 등) 정보주체는 개인정보처리자에게 처리정지를 요구할 수 있다.",
            (PRIVACY_LAW.law_id, "제58조"): "제58조(적용의 일부 제외) 제25조제1항에 따라 공개된 장소에 고정형 영상정보처리기기를 설치ㆍ운영하여 처리되는 개인정보에 대하여는 제34조를 적용하지 아니한다.",
            (NETWORK_LAW.law_id, "제50조"): "제50조(영리목적의 광고성 정보 전송 제한) 영리목적의 광고성 정보를 전송하려면 수신자의 사전 동의 등을 갖추어야 한다.",
            (NETWORK_LAW.law_id, "제50조의8"): "제50조의8(수신동의의 철회 등) 수신자는 광고성 정보 수신동의를 철회할 수 있다.",
        }

    def resolve_law_family(self, law_family: str) -> Optional[ResolvedLaw]:
        return self.laws.get(law_family)

    def get_article(self, law: ResolvedLaw, article_no: str) -> Dict[str, Any]:
        article_text = self.articles.get((law.law_id, article_no), "")
        return {
            "law_id": law.law_id,
            "law_name": law.law_name,
            "article_no": article_no,
            "found": bool(article_text),
            "article_text": article_text,
            "article_text_excerpt": article_text[:240],
            "matched_via": "fake",
            "source": {},
            "article_link": f"{law.law_link}/{article_no}",
            "raw": {"article_text": article_text},
        }

    def find_article_by_keywords(self, law: ResolvedLaw, keywords):
        if law.law_id == PRIVACY_LAW.law_id and "수집이용" in keywords:
            return self.get_article(law, "제15조")
        if law.law_id == NETWORK_LAW.law_id and "광고성정보전송" in keywords:
            return self.get_article(law, "제50조")
        return None

    def get_version(self, law: ResolvedLaw) -> Dict[str, Any]:
        return {
            "source_target": "law_fallback",
            "effective_date": "20251002",
            "promulgation_date": "20250401",
            "revision_type": "일부개정",
            "raw": {},
        }

    def search_law_raw(self, query: str) -> Dict[str, Any]:
        matched = []
        for law in self.laws.values():
            if query in law.law_name or law.law_name in query:
                matched.append({"법령ID": law.law_id, "법령명한글": law.law_name})
        return {"LawSearch": {"law": matched}}

    def get_article_raw(self, law_id: str, article_no: str) -> Dict[str, Any]:
        law = next((item for item in self.laws.values() if item.law_id == law_id), None)
        if law is None:
            return {"law_id": law_id, "article_no": article_no, "found": False, "article_text": ""}
        return self.get_article(law, article_no)

    def get_version_raw(self, law_id: str) -> Dict[str, Any]:
        return {"law_id": law_id, "version_fields": {"시행일자": "20251002"}}

    def validate_article_raw(self, law_id: str, article_no: str) -> Dict[str, Any]:
        return {"law_id": law_id, "article_no": article_no, "is_valid": (law_id, article_no) in self.articles}

    def search_precedent_raw(self, query: str) -> Dict[str, Any]:
        return {"PrecSearch": {"prec": [{"판례일련번호": "123", "사건명": "개인정보 사건", "사건번호": "2025다12345"}]}}

    def get_precedent_raw(self, precedent_id: str) -> Dict[str, Any]:
        return {"precedent_id": precedent_id, "사건명": "개인정보 사건", "사건번호": "2025다12345"}


def ollama_success_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"response": json.dumps(payload, ensure_ascii=False)}
