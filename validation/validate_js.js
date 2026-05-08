const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, '..', 'ui', 'dashboard_template.html');
const content = fs.readFileSync(filePath, 'utf8');

// Extract script content
const scriptMatch = content.match(/<script>([\s\S]*?)<\/script>/);
if (scriptMatch) {
    const script = scriptMatch[1];
    try {
        // Simple evaluation attempt or use a parser
        // new Function(script); // This might be too dangerous or fail due to window/document
        console.log("Script block found. Length:", script.length);
        
        // Check for unbalanced braces
        let openBraces = 0;
        let openBrackets = 0;
        let openParens = 0;
        for (let char of script) {
            if (char === '{') openBraces++;
            if (char === '}') openBraces--;
            if (char === '[') openBrackets++;
            if (char === ']') openBrackets--;
            if (char === '(') openParens++;
            if (char === ')') openParens--;
        }
        console.log("Braces:", openBraces, "Brackets:", openBrackets, "Parens:", openParens);
        if (openBraces !== 0 || openBrackets !== 0 || openParens !== 0) {
            console.error("ERROR: Unbalanced delimiters found!");
        } else {
            console.log("SUCCESS: Delimiters seem balanced.");
        }
    } catch (e) {
        console.error("ERROR in script block:", e.message);
    }
} else {
    console.error("ERROR: No script block found.");
}
