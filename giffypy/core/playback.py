# GiffyPy - Video editor
# Copyright (C) 2026 Faseeh Zaman F S
# SPDX-License-Identifier: GPL-3.0-only

"""Clip speed -> live-preview playback rate.

The export bakes each clip's speed into its filter graph. The preview can't
bake anything: it plays the source media itself, so it has to tell the media
player how fast to run. Both the editor (starting playback, crossing into the
next clip, dragging the slider) and the preview manager (seeking) go through
this module so the two paths can never disagree about what a clip's speed is.
"""

from .constants import SPEED_MAX, SPEED_MIN


def clip_speed(seg):
    """The speed a clip plays at, clamped to what the slider allows."""
    return max(SPEED_MIN, min(SPEED_MAX, seg[2]))


def sync_rate(player, seg):
    """Make `player` play `seg` at its clip speed (no-op when already in sync)."""
    sp = clip_speed(seg)
    if abs(player.playbackRate() - sp) > 1e-6:
        player.setPlaybackRate(sp)
