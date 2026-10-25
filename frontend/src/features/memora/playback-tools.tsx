"use client";

import { useEffect, useRef, useState } from "react";
import { adjacentSegment, loopRange, segmentAt } from "./playback";
import type { Segment } from "./api";
import s from "./transcript-tools.module.css";

export function PlaybackTools({
  getAudio,
  segments,
  selectedStart,
  onPosition,
  english,
}: {
  getAudio: () => HTMLAudioElement | null;
  segments: Segment[];
  selectedStart: number | null;
  onPosition: (time: number) => void;
  english: boolean;
}) {
  const [loop, setLoop] = useState<{ start: number; end: number } | null>(null);
  const [message, setMessage] = useState("");
  const loopRef = useRef(loop);
  useEffect(() => {
    loopRef.current = loop;
  }, [loop]);
  useEffect(() => {
    const player = getAudio();
    if (!player) return;
    let frame = 0;
    let published = -1;
    function update() {
      if (!player) return;
      const bounds = loopRef.current;
      if (bounds && player.currentTime >= bounds.end)
        player.currentTime = bounds.start;
      const tick = Math.floor(player.currentTime * 4);
      if (tick !== published) {
        published = tick;
        onPosition(player.currentTime);
      }
    }
    function animate() {
      update();
      frame = requestAnimationFrame(animate);
    }
    function play() {
      cancelAnimationFrame(frame);
      animate();
    }
    function pause() {
      cancelAnimationFrame(frame);
      update();
    }
    function externalSeek() {
      loopRef.current = null;
      setLoop(null);
    }
    player.addEventListener("memora:seek-source", externalSeek);
    player.addEventListener("timeupdate", update);
    player.addEventListener("seeked", update);
    player.addEventListener("play", play);
    player.addEventListener("pause", pause);
    function ended() {
      if (loopRef.current && player) {
        player.currentTime = loopRef.current.start;
        void player.play().catch(() => {});
      } else pause();
    }
    player.addEventListener("ended", ended);
    if (!player.paused) play();
    return () => {
      cancelAnimationFrame(frame);
      player.removeEventListener("memora:seek-source", externalSeek);
      player.removeEventListener("timeupdate", update);
      player.removeEventListener("seeked", update);
      player.removeEventListener("play", play);
      player.removeEventListener("pause", pause);
      player.removeEventListener("ended", ended);
    };
  }, [getAudio, onPosition]);
  function playAt(time: number) {
    const player = getAudio();
    if (!player) return;
    setLoop(null);
    loopRef.current = null;
    player.currentTime = Math.max(0, time);
    void player
      .play()
      .catch(() =>
        setMessage(
          english
            ? "Use the audio player to start playback."
            : "Utilisez le lecteur audio pour démarrer la lecture.",
        ),
      );
  }
  function move(direction: -1 | 1) {
    const next = adjacentSegment(
      segments,
      getAudio()?.currentTime || 0,
      direction,
    );
    if (next) playAt(next.start);
  }
  function toggleLoop() {
    if (loop) {
      setLoop(null);
      loopRef.current = null;
      return;
    }
    const player = getAudio();
    const selected =
      segments.find((segment) => segment.start === selectedStart) ||
      segmentAt(segments, player?.currentTime || 0);
    const bounds = loopRange(selected, player?.duration || 0);
    if (!player || !bounds) {
      setMessage(
        english
          ? "Select a passage and wait for the audio to load."
          : "Sélectionnez un passage et attendez le chargement de l’audio.",
      );
      return;
    }
    setMessage("");
    setLoop(bounds);
    loopRef.current = bounds;
    player.currentTime = bounds.start;
    void player
      .play()
      .catch(() =>
        setMessage(
          english
            ? "Use the audio player to start playback."
            : "Utilisez le lecteur audio pour démarrer la lecture.",
        ),
      );
  }
  return (
    <div
      role="group"
      className={s.playback}
      aria-label={
        english
          ? "Transcription playback tools"
          : "Outils de lecture de transcription"
      }
      onKeyDown={(event) => {
        if (
          !event.altKey ||
          event.target instanceof HTMLInputElement ||
          event.target instanceof HTMLTextAreaElement ||
          event.target instanceof HTMLSelectElement
        )
          return;
        if (event.code === "ArrowLeft") {
          event.preventDefault();
          move(-1);
        }
        if (event.code === "ArrowRight") {
          event.preventDefault();
          move(1);
        }
        const player = getAudio();
        if (event.code === "Space" && player) {
          event.preventDefault();
          if (player.paused) void player.play().catch(() => {});
          else player.pause();
        }
      }}
      tabIndex={0}
    >
      <div className={s.actions}>
        <button className={s.button} onClick={() => move(-1)}>
          {english ? "Previous passage" : "Passage précédent"}
        </button>
        <button
          className={s.button}
          onClick={() => playAt((getAudio()?.currentTime || 0) - 3)}
        >
          {english ? "Back 3 seconds" : "Reculer de 3 secondes"}
        </button>
        <button className={s.button} onClick={() => move(1)}>
          {english ? "Next passage" : "Passage suivant"}
        </button>
        <button className={s.button} aria-pressed={!!loop} onClick={toggleLoop}>
          {loop
            ? english
              ? "Stop looping"
              : "Arrêter la boucle"
            : english
              ? "Loop passage"
              : "Écouter le passage en boucle"}
        </button>
        <label className={s.speed}>
          {english ? "Speed" : "Vitesse"}{" "}
          <select
            className={s.select}
            aria-label={english ? "Playback speed" : "Vitesse de lecture"}
            defaultValue="1"
            onChange={(event) => {
              const player = getAudio();
              if (player) player.playbackRate = Number(event.target.value);
            }}
          >
            {[0.5, 0.75, 1, 1.25, 1.5, 2].map((rate) => (
              <option key={rate} value={rate}>
                {rate}×
              </option>
            ))}
          </select>
        </label>
      </div>
      <small className={s.shortcuts}>
        {english
          ? "While this toolbar is focused: Alt + ← / → changes passage; Alt + Space plays or pauses."
          : "Dans cette barre : Alt + ← / → change de passage ; Alt + Espace lance ou suspend la lecture."}
      </small>
      {message && (
        <p className={s.status} role="status">
          {message}
        </p>
      )}
    </div>
  );
}
