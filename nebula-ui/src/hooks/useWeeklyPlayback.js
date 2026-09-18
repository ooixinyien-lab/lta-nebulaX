import { useState, useEffect, useRef, useCallback } from "react";

export function useWeeklyPlayback(currentWeek, setWeek, horizonWeeks = 30) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1); // 0.5, 1, 2
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

    const intervalMs = Math.round(1250 / speed);
    timerRef.current = setInterval(() => {
      setWeek((prevWeek) => {
        if (prevWeek >= horizonWeeks) {
          stop();
          return prevWeek;
        }
        return prevWeek + 1;
      });
    }, intervalMs);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [isPlaying, speed, horizonWeeks, setWeek, stop]);

  return { isPlaying, play, stop, toggle, speed, setSpeed };
}
