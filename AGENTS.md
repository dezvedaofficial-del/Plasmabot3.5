---
trigger: always_on
---

# COGNITIVE ARCHITECTURE

## Intelligence Amplification
* **Multi-dimensional reasoning**: Apply parallel logical, mathematical, and creative analysis paths
* **Contextual memory retention**: Maintain session-long context awareness with priority weighting
* **Progressive refinement**: Iteratively improve solutions through self-evaluation cycles
* **Pattern synthesis**: Extract meta-patterns from code structures to inform future decisions
* **Confidence calibration**: Require 89% confidence threshold before implementing changes:
  - Clearly understand the context and requirements
  - Verify the expected effectiveness of the solution
  - Ask clarifying questions until confident
  - Apply domain-specific validation checks

## Decision-Making Framework
* **Risk-weighted evaluation**: Assess potential negative impacts before any change
* **Minimal intervention principle**: Never make more than necessary changes to achieve the desired result
* **Scope isolation**: Never make changes to files that are not directly related to the current task
* **Impact prediction**: Forecast cascading effects of modifications
* **Rollback readiness**: Always maintain reversibility of changes

---

# TECHNICAL EXCELLENCE

## Language & Platform Standards
* **Primary language**: Python (mandatory)
* **Communication language**: English (strictly enforced)
* **Advanced technology priority**: Always use the most advanced solution/technology available for the language
* **Compatibility validation**: Verify all dependencies and platform requirements

## Code Architecture Principles
* **Modular decomposition**: Organize code and file structure by clearly separated modules grouped by capability or responsibility
* **Granular methodology**: Balance minimalism with functional modularity through disaggregation
* **Scalable design**: Ensure architecture supports future enhancement without refactoring
* **Performance optimization**: Prioritize computational efficiency in all implementations
* **Thread-safety**: Implement concurrent-safe patterns where applicable

## Code Quality Standards
* **Clean code compliance**: Follow PEP 8 and language-specific best practices
* **Semantic naming**: Use descriptive variable and function names that reflect their purpose
* **Type safety**: Use type hints to improve code readability and catch errors early
* **File size management**: Maximum 500 lines of code per file; refactor through modular division if exceeded
* **Import hygiene**: Use clear, consistent imports (prefer relative imports within packages)
* **Error handling**: Implement comprehensive exception handling with specific error types

## Security & Safety Protocols
* **Prohibited operations**: Never use `eval`, `exec`, `os.system` - security vulnerabilities
* **Import restrictions**: Never use `import *` - namespace pollution prevention
* **Exception specificity**: Never use bare `except:` or `except Exception` - debugging impediment
* **Input validation**: Sanitize all external inputs and user data
* **Resource management**: Properly handle file descriptors, network connections, and memory

---

# DOCUMENTATION & EXPLAINABILITY

## Code Documentation Standards
* **Comprehensive docstrings**: Document all functions, classes, and modules with purpose, parameters, returns, and examples
* **Inline commentary**: Comment non-obvious code ensuring understanding by mid-level developers
* **Reasoning exposition**: Add inline `# Reason:` comments explaining the why, not just the what
* **Algorithm explanation**: Document complex mathematical or algorithmic implementations
* **API documentation**: Maintain up-to-date interface documentation

## Knowledge Management
* **Assumption validation**: Never assume missing context - ask questions if uncertain
* **Factual accuracy**: Never hallucinate libraries or functions - only use known, verified packages
* **Path verification**: Always confirm file paths and module names exist before referencing
* **Version awareness**: Track dependency versions for reproducibility
* **Change documentation**: Maintain changelog for significant modifications

---

# USER EXPERIENCE & INTERACTION

## Status Reporting & Visibility
* **Progressive disclosure**: Provide detailed status for computationally intensive operations

## Consistency & Coherence
* **Information integrity**: Preserve consistency and coherence of program outputs
* **Interface uniformity**: Maintain consistent UI/UX patterns across components
* **Data flow transparency**: Ensure predictable data transformations and state changes
* **Behavioral reliability**: Guarantee consistent responses to identical inputs

---

# ADVANCED CONSTRAINTS & PROHIBITIONS

## Dependency Management
* **Explicit semantic omission**: Consciously avoid unnecessary dependencies in software planning
* **Framework restrictions**: 
  - Prohibited: TensorFlow, Docker Desktop
  - Permitted: Docker Engine (terminal-only)
  - Alternative requirement: Use equivalent tools to achieve objectives
* **Capability preservation**: Never delete features or reduce capabilities, including non-integrated components
* **Mathematical fidelity**: 100% fidelity to original mathematics and architecture - never simplify or remove logic, only port or enhance
* **Zero circular imports**: Maintain clean dependency hierarchy to prevent circular imports

## Data Integrity Requirements
* **Authenticity mandate**: Never use mocks, data simulation, or random data generation as fallback or main data source
* **Real data requirement**: All testing and operations must use authentic data sources
* **Verification protocols**: Implement data source validation and integrity checks
* **Source traceability**: Maintain clear data lineage and provenance tracking

## Professional Standards
* **Visual cleanliness**: Strictly prohibited to use emojis in any part of the code
* **End-to-end validation**: Check CLI metrics and exposures for every backend implementation
* **Double-checking development**: Verify all integrations meet requirements specifications
* **Production readiness**: Ensure all code meets production-quality standards

---

# PERFORMANCE & OPTIMIZATION

## Computational Efficiency
* **Algorithm optimization**: Choose optimal time and space complexity solutions
* **Memory management**: Implement efficient memory usage patterns and garbage collection awareness
* **Caching strategies**: Utilize appropriate caching mechanisms for repeated computations
* **Lazy evaluation**: Implement deferred computation where beneficial

# CONTINUOUS IMPROVEMENT

## Learning & Adaptation
* **Pattern recognition**: Learn from successful patterns and anti-patterns
* **Technology evolution**: Stay current with language and framework improvements
* **Knowledge synthesis**: Combine insights from multiple projects to improve general approach

## Quality Assurance
* **Testing protocols**: Implement comprehensive unit, integration, and system testing
* **Code review standards**: Apply rigorous review criteria for all changes
* **Regression prevention**: Ensure new changes don't break existing functionality
* **Documentation maintenance**: Keep all documentation current with code changes
* **Refactoring discipline**: When improving code structure without changing framework principles

---

# ADVANCED INTEGRATION PROTOCOLS

## System Integration
* **Interface standardization**: Define clear, consistent interfaces between components
* **Event-driven architecture**: Implement loose coupling through event-based communication
* **State management**: Centralize and control application state changes
* **Configuration management**: Externalize configuration with environment-specific overrides

## Deployment & Operations
* **Environment parity**: Maintain consistency across development, testing, and production
* **Graceful degradation**: Design systems to handle partial failures elegantly
* **Logging strategy**: Implement structured, searchable logging with appropriate levels
* **Rollback procedures**: Maintain clear procedures for reverting problematic changes

<MANDATORY RULE> To every creation or modification of any source-code file whose size, diff, or future state could exceed ≈ 200 lines OR ≈ 4 kB:

1. Prevent runtime failures caused by; Request / response timeouts, Context-cancellation errors, “Timeout while reading body” or token-limit errors, Partial writes that corrupt the file.
2. Required Procedure; Chunk the entire creation or diff into ≤ 200-line or ≤ 4 kB blocks, Write / apply each chunk sequentially, starting from the top of the file.
3. After every chunk; 
 a. Re-read the file (or the affected lines) to confirm the write succeeded.
 b. Validate syntax (compile, lint, or minimal sanity check) before continuing.
4. Never attempt a single-shot write of the full file or of a large diff.
5. Abort and report if any chunk fails validation; do not proceed to the next chunk until the current one is 100 % confirmed.