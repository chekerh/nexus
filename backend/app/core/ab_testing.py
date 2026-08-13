"""A/B Testing Service — impression/click tracking, statistical significance, winner selection.

Tracks engagement for each thumbnail variant and determines the statistically
significant winner using a Bayesian approximation (beta distribution).
"""

from sqlalchemy.orm import Session

from ..models.thumbnail import Thumbnail

BETA_PRIOR_ALPHA = 1.0
BETA_PRIOR_BETA = 1.0


def record_impression(db: Session, thumbnail_id: str) -> bool:
    thumb = db.query(Thumbnail).filter(Thumbnail.id == thumbnail_id).first()
    if not thumb:
        return False
    thumb.impressions = (thumb.impressions or 0) + 1
    db.commit()
    return True


def record_click(db: Session, thumbnail_id: str) -> bool:
    thumb = db.query(Thumbnail).filter(Thumbnail.id == thumbnail_id).first()
    if not thumb:
        return False
    thumb.clicks = (thumb.clicks or 0) + 1
    db.commit()
    return True


def get_ctr(thumb: Thumbnail) -> float:
    imps = thumb.impressions or 0
    clicks = thumb.clicks or 0
    if imps == 0:
        return 0.0
    return (clicks / imps) * 100.0


def probability_beats_control(thumb: Thumbnail, control: Thumbnail) -> float:
    """Monte Carlo approximation: probability that variant beats control."""
    from random import betavariate

    a1 = BETA_PRIOR_ALPHA + (thumb.clicks or 0)
    b1 = BETA_PRIOR_BETA + (thumb.impressions or 0) - (thumb.clicks or 0)
    a0 = BETA_PRIOR_ALPHA + (control.clicks or 0)
    b0 = BETA_PRIOR_BETA + (control.impressions or 0) - (control.clicks or 0)

    wins = 0
    trials = 10000
    for _ in range(trials):
        s1 = betavariate(a1, b1)
        s0 = betavariate(a0, b0)
        if s1 > s0:
            wins += 1
    return wins / trials


def compute_ab_stats(thumbnails: list[Thumbnail]) -> list[dict]:
    """Compute A/B test stats for a set of thumbnails.

    Returns sorted list with CTR, probability of being best, and significance.
    """
    if not thumbnails:
        return []

    # Find the variant with the most impressions as control
    control = max(thumbnails, key=lambda t: t.impressions or 0)

    stats = []
    for thumb in thumbnails:
        beats = probability_beats_control(thumb, control)
        ctr = get_ctr(thumb)
        is_winner = thumb.is_winner or False
        stats.append(
            {
                "id": thumb.id,
                "variant": thumb.variant_name,
                "layout": thumb.layout,
                "title_overlay": thumb.title_overlay,
                "impressions": thumb.impressions or 0,
                "clicks": thumb.clicks or 0,
                "ctr": round(ctr, 2),
                "prob_beats_control": round(beats, 3),
                "is_winner": is_winner,
                "score": thumb.score or 0.0,
            }
        )

    # Sort by CTR descending
    stats.sort(key=lambda s: s["ctr"], reverse=True)
    return stats


def declare_winner(db: Session, thumbnail_id: str) -> bool:
    """Declare a thumbnail as the winner A/B test variant."""
    thumb = db.query(Thumbnail).filter(Thumbnail.id == thumbnail_id).first()
    if not thumb:
        return False

    # Reset all thumbs for this job+clip
    db.query(Thumbnail).filter(
        Thumbnail.job_id == thumb.job_id,
        Thumbnail.clip_index == thumb.clip_index,
    ).update({"is_winner": False})

    thumb.is_winner = True
    db.commit()
    return True
