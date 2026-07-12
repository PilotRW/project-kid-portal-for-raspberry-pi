from app.services.youtube_api import YouTubeApiService


def test_candidates_skip_non_embeddable_results():
    service = YouTubeApiService(api_key="test")
    search_items = [
        {
            "id": {"videoId": "allowed"},
            "snippet": {
                "title": "Allowed",
                "description": "",
                "channelId": "channel-a",
                "channelTitle": "Channel A",
                "thumbnails": {"high": {"url": "https://i.ytimg.com/high.jpg"}},
            },
        },
        {
            "id": {"videoId": "blocked"},
            "snippet": {
                "title": "Blocked",
                "description": "",
                "channelId": "channel-b",
                "channelTitle": "Channel B",
                "thumbnails": {},
            },
        },
    ]
    details_by_id = {
        "allowed": {"status": {"embeddable": True}, "contentDetails": {"duration": "PT3M"}},
        "blocked": {"status": {"embeddable": False}, "contentDetails": {"duration": "PT3M"}},
    }

    candidates = [
        service._candidate_from_item(item, details_by_id)
        for item in search_items
        if details_by_id.get(item.get("id", {}).get("videoId"), {}).get("status", {}).get("embeddable", True)
    ]

    assert [candidate.video_id for candidate in candidates] == ["allowed"]
    assert candidates[0].thumbnail_url == "https://i.ytimg.com/high.jpg"
