import React from "react"

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}

export function Card({ className = "", children, ...props }: CardProps) {
  return (
    <div className={`bg-bg-1 rounded-lg border border-border/10 ${className}`} {...props}>
      {children}
    </div>
  )
}

// Compound subcomponents — shadcn/Chakra/Mantine conventions all expose these.
// Exporting them prevents the "no exported member CardContent" hallucination
// cascade we hit in gallery builds.

export function CardHeader({ className = "", children, ...props }: CardProps) {
  return (
    <div className={`px-6 py-4 border-b border-border/10 ${className}`} {...props}>
      {children}
    </div>
  )
}

export function CardTitle({ className = "", children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={`text-lg font-semibold ${className}`} {...props}>
      {children}
    </h3>
  )
}

export function CardDescription({ className = "", children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={`text-sm text-muted ${className}`} {...props}>
      {children}
    </p>
  )
}

export function CardContent({ className = "", children, ...props }: CardProps) {
  return (
    <div className={`px-6 py-4 ${className}`} {...props}>
      {children}
    </div>
  )
}

export function CardFooter({ className = "", children, ...props }: CardProps) {
  return (
    <div className={`px-6 py-4 border-t border-border/10 flex items-center ${className}`} {...props}>
      {children}
    </div>
  )
}

export default Card
