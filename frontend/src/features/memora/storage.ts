// Les données audio restent sur cet appareil jusqu’à confirmation de sauvegarde serveur.
export type PendingChunk = {
  key: string;
  meeting: string;
  seq: number;
  blob: Blob;
};
function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("memora-audio", 1);
    request.onupgradeneeded = () =>
      request.result.createObjectStore("chunks", { keyPath: "key" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
export async function saveChunk(meeting: string, seq: number, blob: Blob) {
  const db = await database();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction("chunks", "readwrite");
    tx.objectStore("chunks").put({
      key: `${meeting}:${seq}`,
      meeting,
      seq,
      blob,
    });
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}
export async function pendingChunks(meeting: string): Promise<PendingChunk[]> {
  const db = await database();
  const all = await new Promise<PendingChunk[]>((resolve, reject) => {
    const request = db.transaction("chunks").objectStore("chunks").getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  db.close();
  return all.filter((c) => c.meeting === meeting).sort((a, b) => a.seq - b.seq);
}
export async function removeChunk(key: string) {
  const db = await database();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction("chunks", "readwrite");
    tx.objectStore("chunks").delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}
