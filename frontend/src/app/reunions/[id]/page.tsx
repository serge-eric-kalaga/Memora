import { Suspense } from "react";
import { MeetingPage } from "@/features/memora/app";
type Props = { params: Promise<{ id: string }> };
async function Content({ params }: Props) {
  const { id } = await params;
  return <MeetingPage id={id} />;
}
export default function Page(props: Props) {
  return (
    <Suspense
      fallback={
        <main className="page-shell" style={{ padding: 40 }}>
          Ouverture de la réunion…
        </main>
      }
    >
      <Content {...props} />
    </Suspense>
  );
}
