import { Suspense } from "react";
import { SharedPage } from "@/features/memora/app";
type Props = { params: Promise<{ token: string }> };
async function Content({ params }: Props) {
  const { token } = await params;
  return <SharedPage token={token} />;
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
