import headerLogo from '../../../design/logo/detola-koc-3-header.svg?raw';
import stackLogo from '../../../design/logo/detola-koc-2-stack-discover.svg?raw';

type BrandLogoProps = {
  variant: 'header' | 'stack';
  className?: string;
};

const logoMarkup = {
  header: headerLogo.slice(headerLogo.indexOf('>') + 1, headerLogo.lastIndexOf('</svg>')),
  stack: stackLogo.slice(stackLogo.indexOf('>') + 1, stackLogo.lastIndexOf('</svg>')),
};

const viewBoxes = { header: '0 0 620 80', stack: '0 0 560 170' };

export function BrandLogo({ variant, className = '' }: BrandLogoProps) {
  return <svg
    className={`brand-logo ${className}`}
    xmlns="http://www.w3.org/2000/svg"
    viewBox={viewBoxes[variant]}
    role="img"
    aria-label="DETOLA KOC Discovery"
    dangerouslySetInnerHTML={{ __html: logoMarkup[variant] }}
  />;
}
