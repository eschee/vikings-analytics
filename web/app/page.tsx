import Guide from "@/components/Guide";
import Header from "@/components/Header";
import { MissingDataError, loadPageData } from "@/lib/data";

/** The one page. A Server Component: it reads the exported JSON on the server
 *  and passes a small view model to the client, so the browser never receives
 *  the ~290 KB export or nine weeks of games it will not show. */

export default async function Page() {
  let data;
  try {
    data = await loadPageData("MIN");
  } catch (error) {
    if (error instanceof MissingDataError) {
      return (
        <main className="px-5 py-10">
          <h1 className="font-display text-2xl font-bold text-brand">
            No data yet
          </h1>
          <p className="mt-3 text-sm text-muted">{error.message}</p>
        </main>
      );
    }
    throw error;
  }

  return (
    <>
      <Header data={data} />
      <Guide data={data} />
    </>
  );
}
