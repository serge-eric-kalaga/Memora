import { EmailVerification } from "@/features/auth/email-verification";
export const metadata = {
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export default function ConfirmEmailPage() {
  return <EmailVerification />;
}
