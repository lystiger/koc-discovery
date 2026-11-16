VIDEOS_PER_KOC = 3


def tier_for(followers, tiers):
    """The tier covering followers; outside the rate card, the nearest tier."""
    return next((t for t in tiers if t["min_followers"] <= followers <= t["max_followers"]), None) or min(
        tiers, key=lambda t: min(abs(followers - t["min_followers"]), abs(followers - t["max_followers"])))


def video_total(vnd_per_video):
    return int(vnd_per_video) * VIDEOS_PER_KOC


def creator_cost(followers, tiers):
    """The one cost model (pipeline S4/options, CLI precheck, web): tier vnd_per_video x 3 videos, never 0."""
    return video_total(tier_for(followers, tiers)["vnd_per_video"])
