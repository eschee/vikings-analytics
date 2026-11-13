import { redirect } from "next/navigation";

/** The root sends you to the Vikings, since that is whose guide this is.
 *  Every team lives at /<abbr>, validated against the allowlist there. */
export default function Home() {
  redirect("/min");
}
