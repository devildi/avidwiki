import SearchInterface from "../components/SearchInterface";
import Navbar from "../components/Navbar";

export default function Home() {
  return (
    <main className="flex flex-col min-h-screen bg-neutral-900 text-neutral-100">
      <Navbar />
      <div className="flex-1">
        <SearchInterface />
      </div>
    </main>
  );
}
