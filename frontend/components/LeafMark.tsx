/** A small crafted leaf/sprout mark — the Leaflet identity (not an emoji). */
export default function LeafMark({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden className={className}>
      {/* leaf body */}
      <path
        d="M20 4C11 4 5 9.4 5 16.5c0 1.2.2 2.3.6 3.3C7.4 14.8 11.6 11 17 9.6c-4.2 2-7.4 5.4-9 9.8 1 .4 2.1.6 3.3.6C18.6 20 24 14 20 4Z"
        fill="currentColor"
      />
    </svg>
  );
}
