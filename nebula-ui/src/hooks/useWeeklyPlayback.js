import { useState, useEffect, useRef, useCallback } from "react";
import { PLAYBACK_INTERVAL_MS } from "../network/mapConstants";

export function useWeeklyPlayback(currentWeek, setWeek, horizonWeeks = 30) {
  const [isPlaying, setIsPlaying] = useState(false);
  const timerRef = useRef(null);

  const stop = useCallback(() => {
    setIsPlaying(false);
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const play = useCallback(() => {
    // If currently at the end, jump to start before playing
    if (currentWeek >= horizonWeeks) {
      setWeek(1);
    }
    setIsPlaying(true);
  }, [currentWeek, horizonWeeks, setWeek]);

  const toggle = useCallback(() => {
    if (isPlaying) {
      stop();
    } else {
      play();
    }
  }, [isPlaying, play, stop]);

  useEffect(() => {
    if (!isPlaying) {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
      return;
    }

    timerRef.current = setInterval(() => {
      setWeek((prevWeek) => {
        if (prevWeek >= horizonWeeks) {
          stop();
          return prevWeek;
        }
        return prevWeek + 1;
      });
    }, PLAYBACK_INTERVAL_MS);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [isPlaying, horizonWeeks, setWeek, stop]);

  return { isPlaying, play, stop, toggle };
}
