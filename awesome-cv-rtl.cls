%% Start of file `awesome-cv-rtl.cls'.
% Awesome CV RTL Class File - Right-to-Left (RTL) support for Persian/Arabic
%
% This class extends awesome-cv.cls to add RTL and Farsi support.
% It loads the base class and adds:
%   - polyglossia for Persian language support
%   - bidi for bidirectional text handling
%   - Farsi-capable fonts (Vazirmatn as primary font)
%
% Requirements:
%   - XeLaTeX compiler
%   - Vazirmatn font (or alternative Persian font installed on system)
%   - polyglossia and bidi packages
%
% Class license:
% LPPL v1.3c (http://www.latex-project.org/lppl)
%


%-------------------------------------------------------------------------------
%                Identification
%-------------------------------------------------------------------------------
\ProvidesClass{awesome-cv-rtl}[2025/01/08 v1.0 Awesome CV RTL Class]
\NeedsTeXFormat{LaTeX2e}


%-------------------------------------------------------------------------------
%                Class options
%-------------------------------------------------------------------------------
% Pass all options to the base awesome-cv class
\DeclareOption*{%
  \PassOptionsToClass{\CurrentOption}{./awesome-cv}
}
\ProcessOptions\relax


%-------------------------------------------------------------------------------
%                Load base class
%-------------------------------------------------------------------------------
\LoadClass{./awesome-cv}


%-------------------------------------------------------------------------------
%                RTL and Persian language support
%-------------------------------------------------------------------------------
% Load polyglossia for multilingual support
\RequirePackage{polyglossia}

% Set Persian as the main language with RTL direction
\setmainlanguage[numerals=western]{persian}
% Keep English as secondary language for Latin text
\setotherlanguage{english}

% Load bidi package for bidirectional text (loaded automatically by polyglossia, but ensure it's available)
% Note: bidi is typically loaded by polyglossia when RTL language is set


%-------------------------------------------------------------------------------
%                RTL-aware font configuration
%-------------------------------------------------------------------------------
% Define Persian font family using Vazirmatn (a modern, open-source Persian font)
% Vazirmatn is available at: https://github.com/rastikerdar/vazirmatn
% If Vazirmatn is not available, fallback options are provided

\IfFontExistsTF{Vazirmatn}{%
  % Vazirmatn font is available - use it
  \newfontfamily\persianfont[Script=Arabic,Scale=1.0]{Vazirmatn}
  \setmainfont[Script=Arabic,Scale=1.0]{Vazirmatn}
}{%
  \IfFontExistsTF{XB Niloofar}{%
    % XB Niloofar fallback
    \newfontfamily\persianfont[Script=Arabic,Scale=1.0]{XB Niloofar}
    \setmainfont[Script=Arabic,Scale=1.0]{XB Niloofar}
  }{%
    \IfFontExistsTF{B Nazanin}{%
      % B Nazanin fallback
      \newfontfamily\persianfont[Script=Arabic,Scale=1.0]{B Nazanin}
      \setmainfont[Script=Arabic,Scale=1.0]{B Nazanin}
    }{%
      % Final fallback - use system default with Arabic script
      \ClassWarning{awesome-cv-rtl}{%
        No Persian font found (Vazirmatn, XB Niloofar, B Nazanin).
        Please install Vazirmatn from https://github.com/rastikerdar/vazirmatn
        or another Persian-capable font.
        Using system default which may not render Persian text correctly.
      }
    }%
  }%
}


%-------------------------------------------------------------------------------
%                RTL-aware header and style adjustments
%-------------------------------------------------------------------------------
% Redefine header name style for RTL - swap first/last name order for Persian convention
\renewcommand*{\headerfirstnamestyle}[1]{{\fontsize{32pt}{1em}\color{graytext} #1}}
\renewcommand*{\headerlastnamestyle}[1]{{\fontsize{32pt}{1em}\bfseries\color{text} #1}}

% Adjust social separator for RTL
\renewcommand{\acvHeaderSocialSep}{\quad\textbar\quad}


%-------------------------------------------------------------------------------
%                RTL-aware column types for tables
%-------------------------------------------------------------------------------
% Redefine column types for RTL alignment
% In RTL, "left" becomes visually "right" and vice versa
\renewcommand{\newcolumntype}{}
\newcolumntype{L}[1]{>{\raggedleft\let\newline\\\arraybackslash\hspace{0pt}}m{#1}}
\newcolumntype{R}[1]{>{\raggedright\let\newline\\\arraybackslash\hspace{0pt}}m{#1}}
\newcolumntype{C}[1]{>{\centering\let\newline\\\arraybackslash\hspace{0pt}}m{#1}}


%-------------------------------------------------------------------------------
%                Commands for RTL-aware CV entries
%-------------------------------------------------------------------------------
% Redefine cventry for RTL layout
% Usage: \cventry{<position>}{<title>}{<location>}{<date>}{<description>}
\renewcommand*{\cventry}[5]{%
  \vspace{-2.0mm}
  \setlength\tabcolsep{0pt}
  \setlength{\extrarowheight}{0pt}
  % Swap column widths for RTL: date on left, content on right
  \begin{tabular*}{\textwidth}{@{\extracolsep{\fill}} R{4.5cm} L{\textwidth - 4.5cm}}
    \entrydatestyle{#4} & \ifempty{#2#3}
      {\entrypositionstyle{#1}}
      {\entrytitlestyle{#2} \\
      \entrydatestyle{} & \entrypositionstyle{#1}} \\
    & \ifempty{#3}{}{\entrylocationstyle{#3}} \\
    \ifstrempty{#5}
      {}
      {& \multicolumn{1}{L{\textwidth - 4.5cm}}{\descriptionstyle{#5}} \\}
  \end{tabular*}%
}


%-------------------------------------------------------------------------------
%                End of RTL class file
%-------------------------------------------------------------------------------
