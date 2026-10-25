"use client";
import Image from "next/image";
import { useState } from "react";
import type { CurrentUser } from "@/lib/api/types";
export function Avatar({
  user,
  large = false,
}: {
  user: CurrentUser;
  large?: boolean;
}) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const size = large ? 96 : 40;
  const photo = user.profile_photo_url && user.profile_photo_url !== failedUrl;
  return (
    <span className={`avatar${large ? " avatar-large" : ""}`}>
      {photo ? (
        <Image
          src={user.profile_photo_url!}
          alt=""
          width={size}
          height={size}
          unoptimized
          onError={() => setFailedUrl(user.profile_photo_url)}
        />
      ) : (
        <span aria-hidden="true">
          {user.username.slice(0, 2).toUpperCase()}
        </span>
      )}
    </span>
  );
}
