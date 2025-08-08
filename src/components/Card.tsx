import React from "react";

type CardProps = {
  title?: string;
  body?: string;
  className?: string;
  onClick?: () => void;
};

const Card: React.FC<CardProps> = ({ title = "Title", body = "Copy", className = "", onClick }) => {
  return (
    <div
      onClick={onClick}
      className={`rounded-xl bg-white/10 text-[#FAFAFA] p-4 flex flex-col items-start gap-8 cursor-pointer transition-transform duration-200 ease-in-out hover:scale-[1.02] ${className}`}    >
      <div className="text-sm font-mono tracking-wide">{title}</div>
      <div className="text-2xl font-bold leading-tight">{body}</div>
    </div>
  );
};

export default Card;
