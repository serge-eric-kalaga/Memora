import { Recovery } from "@/features/auth/recovery";
export const metadata = {
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export default function RecoveryPage() {
  return <Recovery mode="forgot" />;
}
