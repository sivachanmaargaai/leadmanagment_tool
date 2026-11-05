import { useEffect, useRef } from "react";

export default function PageTransition({ className, children }) {
  const ref = useRef(null);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const animation = ref.current.animate(
      [{ opacity: 0.6, transform: "translateY(4px)" }, { opacity: 1, transform: "translateY(0)" }],
      { duration: 160, easing: "ease-out" }
    );
    return () => animation.cancel();
  }, []);
  return <div ref={ref} className={className}>{children}</div>;
}
