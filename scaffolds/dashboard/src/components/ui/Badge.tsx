export default function Badge({ children, className, ...props }: { children?: React.ReactNode; className?: string; [key: string]: any }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-accent/15 text-accent ${className || ''}`}
      {...props}
    >
      {children}
    </span>
  )
}
