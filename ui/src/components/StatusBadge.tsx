const COLOURS: Record<string, string> = {
  draft:       'bg-gray-700 text-gray-300',
  validating:  'bg-yellow-900 text-yellow-300',
  approved:    'bg-blue-900 text-blue-300',
  deploying:   'bg-orange-900 text-orange-300',
  deployed:    'bg-green-900 text-green-300',
  rejected:    'bg-red-900 text-red-300',
  cancelled:   'bg-gray-800 text-gray-500',
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = COLOURS[status] ?? 'bg-gray-700 text-gray-300';
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}
