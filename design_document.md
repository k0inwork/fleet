# **Jules Workflow Orchestrator: Complete System Design Document**

## **1. Overview**

The **Jules Workflow Orchestrator** is designed to automate the management of AI-driven development workflows. It interacts with **Jules VMs** (Virtual Machines), orchestrates tasks, integrates with **GitHub Actions** when necessary, and handles **Human-in-the-Loop (HIL)** feedback loops.

A key feature of this system is the **chat-based interface**, where **Telegram** or a **web app** acts as the main communication channel for human intervention. The orchestrator allows users to give real-time feedback, approve or reject tasks, and make decisions about workflow progression directly via Telegram or a web-based chat interface.

---

## **2. Architecture & Tech Stack**

### **2.1. Core Technologies**

* **Frontend Framework**: React 18 with TypeScript
* **Build Tool**: Vite (for fast builds)
* **Styling**: Tailwind CSS (utility-first, focusing on performance)
* **State Management**: React Hooks (`useState`, `useEffect`, `useCallback`)
* **AI Integration**: **Google GenAI (Gemini)** for autonomous workflow generation.
* **Communication Channel**: **Telegram** and **Web-based chat interface** for real-time feedback loops with users.
* **GitHub Integration**: **GitHub Actions** to handle specific tasks and produce artifacts that **Jules VMs** cannot generate natively.

### **2.2. Jules-MCP Server**

The **Jules-MCP Server** is a key component that manages **Jules VMs**. It provisions the VMs, runs tasks, and handles task failures and retries. The **orchestrator** communicates with **Jules-MCP** to execute tasks on **Jules VMs** and collect the results.

### **2.3. Telegram Integration**

The orchestrator integrates deeply with **Telegram**, allowing:

1. **Real-time updates** on workflow status.
2. **Human-in-the-Loop (HIL)** notifications, where the system pauses and sends a message to the user to approve or reject a task.
3. **Decision-making** through Telegram, where users can reply with "yes", "no", or provide custom feedback to guide the workflow.

The **Telegram bot** sends rich, contextual messages that explain the current workflow status, logs, and task outcomes. Users can interact directly from within Telegram to make decisions or ask for more information.

---

## **3. Core Domain Models**

### **3.1. Workflows**

A **workflow** is a directed acyclic graph (DAG) consisting of nodes and edges:

* **Nodes** represent discrete tasks or decision points (e.g., execution of a task, waiting for human feedback).
* **Edges** represent the flow of control from one node to another, often based on conditions such as the success or failure of previous tasks.

### **3.2. Sessions (Jules VMs)**

A **session** represents a **Jules VM** running a specific task. Each **Jules VM** works on one repository and one branch at a time and can report on its success or failure.

**States** of **Jules VM Sessions**:

* **PENDING**: The VM is awaiting execution.
* **RUNNING**: The VM is executing the task.
* **SUCCEEDED**: The task completed successfully.
* **FAILED**: The task encountered an error.
* **CANCELED**: The task was canceled by the orchestrator or human feedback.

### **3.3. Agents.md**

Each **Jules VM** has a capability file called **`agents.md`**. This file contains the following information:

* **Capabilities**: The specific tasks that the VM can perform.
* **Fallback**: If the VM cannot handle a task, the orchestrator queries **`agents.md`** for fallback options, such as whether **GitHub Actions** can be used to handle the task instead.

Example snippet from **`agents.md`**:

```yaml
capabilities:
  - task: "Build Android APK"
    supported: false  # VM cannot handle this task
    fallback: "github_actions"  # GitHub Actions is used for this task
  - task: "Run unit tests"
    supported: true  # VM can handle unit tests natively
    fallback: "none"  # No external fallback is needed
```

### **3.4. Orchestrator & Node Types**

The orchestrator manages multiple nodes, each representing different workflow stages. These nodes can be task execution points, decision-making points, or human feedback points.

#### Core Node Types:

1. **`START` Node**: Marks the beginning of the workflow.
2. **`TASK` Node**: Executes tasks on **Jules VMs**.
3. **`LLM_ORCHESTRATOR` Node**: Manages more complex workflows that require multi-step reasoning.
4. **`DECISION` Node**: Makes decisions based on the success/failure of previous tasks.
5. **`APPROVAL` (Human-in-the-Loop) Node**: Pauses the workflow, waiting for human feedback (via Telegram or WebApp).
6. **`END` Node**: Marks the completion of the workflow.

---

## **4. Workflow Execution and State Machines**

### **4.1. Task Node State Machine**

The **TASK** node represents a task executed on a **Jules VM** and has the following states:

* **PENDING**: The task is ready to be executed.
* **RUNNING**: The task is executing.
* **COMPLETED**: The task successfully finished.
* **FAILED**: The task failed.
* **RETRY**: The task needs to be retried.

```typescript
function transitionTaskState(node: NodeState, newState: "RUNNING" | "COMPLETED" | "FAILED" | "RETRY") {
  node.status = newState;
  if (newState === "COMPLETED") {
    moveToNextNode(node);
  } else if (newState === "FAILED") {
    handleFailure(node);
  }
}
```

### **4.2. Human-in-the-Loop (HIL) Node State Machine**

The **HIL** node interacts with the user and has the following states:

* **WAITING**: The node is waiting for feedback.
* **APPROVED**: The task is approved by the user.
* **REJECTED**: The task is rejected, and it either retries or aborts.
* **UNDECIDED**: The user requests more context before deciding.

**Telegram feedback integration** ensures that the **HIL node** sends rich contextual messages with detailed logs and task progress updates.

```typescript
function processHILFeedback(node: NodeState, feedback: "approve" | "reject" | "undecided") {
  switch (feedback) {
    case "approve":
      node.status = "APPROVED";
      moveToNextNode(node);
      break;
    case "reject":
      node.status = "REJECTED";
      restartOrAbortTask(node);
      break;
    case "undecided":
      node.status = "WAITING";
      requestMoreContextFromJulesVM(node);
      break;
  }
}
```

### **4.3. LLM_ORCHESTRATOR Node State Machine**

The **LLM_ORCHESTRATOR** node is responsible for making higher-level decisions. It handles:

* Multi-step task execution.
* Decision-making based on workflow context and external information (such as from **Jules VMs** or **GitHub Actions**).

### **4.4. GitHub Actions Integration**

When **Jules VM** cannot perform a specific task, the orchestrator falls back to **GitHub Actions**. This fallback is explicitly defined in the **`agents.md`** file for each **task** that cannot be handled by the VM. The orchestrator checks the capabilities in **`agents.md`** before deciding whether to trigger a **GitHub Actions** workflow.

Example of GitHub Actions fallback:

```yaml
capabilities:
  - task: "Build Android APK"
    supported: false  # VM cannot handle this task
    fallback: "github_actions"  # Use GitHub Actions for this task
```

When triggered, the orchestrator will execute the appropriate GitHub Actions workflow defined in the project’s **.github** directory.

### **4.5. Dynamic Updates to `agents.md`**

The orchestrator can **dynamically update the `agents.md`** file to reflect any changes in the capabilities of **Jules VMs**. This includes adding new tasks, modifying the fallback behavior, or specifying new integration points (such as additional **GitHub Actions** workflows).

---

## **5. Interaction with Telegram & Chat Interface**

### **5.1. Telegram as a Communication Channel**

**Telegram** serves as a communication channel for the **Human-in-the-Loop (HIL)** nodes. The orchestrator sends rich messages with detailed context, including logs, task statuses, and feedback requests.

* **Task Status Updates**: When a task's state changes (e.g., a **Jules VM** completes a task), **Telegram** sends a notification with the task’s result.
* **Human Feedback**: The **HIL node** sends a request for feedback, asking the user to approve or reject the task. The user can simply reply "yes", "no", or
"undecided," or even ask for more context or logs.

The feedback loop through **Telegram** can work as follows:

* **Approval**: When the user approves the task, the orchestrator moves the workflow forward, either to the next node or back to retry a previous task if needed.
* **Rejection**: If the user rejects the task, the orchestrator may either abort the workflow or retry the task, based on the defined logic.
* **Undecided**: If the user requests more context, the orchestrator fetches additional details from the **Jules VM**, such as logs or other relevant information, and sends it back to the user.

#### **Telegram Integration Example**:

A typical **Telegram message** sent during a **HIL node** interaction might look like this:

```plaintext
⚙️ **Task Update: Build APK**

- Task: Build Android APK on branch `feature/xyz`
- Current Status: **Failed**
- Error Message: `Missing dependencies on VM: xyz`

Do you want to:
1. Retry the task (Yes)
2. Reject and stop the workflow (No)
3. Request more logs/details (Undecided)

Please reply with the corresponding number.
```

---

### **5.2. Chat-based Web Interface**

In addition to **Telegram**, the orchestrator supports a **web-based chat interface** for human feedback. This interface will function similarly to the **Telegram bot**, allowing users to approve or reject tasks, request more context, or provide feedback directly in a browser.

This web interface will be built as part of the **orchestrator** application and offer a similar interaction flow, where users can:

* View real-time status of workflows.
* Request logs, files, or other context needed to make a decision.
* Interact with **HIL nodes** to provide their feedback and make decisions.

The web interface is essentially a mirror of the **Telegram feedback loop**, but it can provide additional visual context (such as logs, graphs, and task status) to help users make more informed decisions.

---

## **6. Workflow Execution and State Machine**

### **6.1. Full Workflow Lifecycle**

The **Jules Workflow Orchestrator** follows a defined lifecycle from initialization through to completion, with feedback loops and decision points integrated at various stages. The lifecycle incorporates:

1. **Task Execution**: **Jules VMs** perform tasks and report back status updates.
2. **Human-in-the-Loop**: When human feedback is required, the system pauses and prompts the user (via **Telegram** or **WebApp**) for a decision.
3. **Decision Making**: The **LLM Orchestrator** decides if a task can proceed based on the capabilities of **Jules VMs** or if a fallback to **GitHub Actions** is required.
4. **Artifacts Generation**: If needed, **Jules VMs** can trigger **GitHub Actions** to generate artifacts that the VM cannot handle natively.
5. **Approval**: After receiving user feedback, the workflow either continues or retries based on the decision.

### **6.2. Node-Level States and Transitions**

Each **workflow node** has a state machine that controls its transitions based on task completion and human feedback. Below are the state transitions for each node type.

#### **TASK Node State Machine**

* **PENDING**: Task is ready to be executed.
* **RUNNING**: Task is executing on **Jules VM**.
* **COMPLETED**: Task finished successfully.
* **FAILED**: Task failed.
* **RETRY**: Task needs to be retried.

Example of state transition:

```typescript
function transitionTaskState(node: NodeState, newState: "RUNNING" | "COMPLETED" | "FAILED" | "RETRY") {
  node.status = newState;
  if (newState === "COMPLETED") {
    moveToNextNode(node);
  } else if (newState === "FAILED") {
    handleFailure(node);
  }
}
```

#### **HIL Node State Machine**

* **WAITING**: The node is waiting for human feedback.
* **APPROVED**: The user approves the task, and the workflow moves forward.
* **REJECTED**: The user rejects the task, triggering a retry or abort.
* **UNDECIDED**: The user requests more context (logs, task status, etc.).

Example of state handling for HIL feedback:

```typescript
function processHILFeedback(node: NodeState, feedback: "approve" | "reject" | "undecided") {
  switch (feedback) {
    case "approve":
      node.status = "APPROVED";
      moveToNextNode(node);
      break;
    case "reject":
      node.status = "REJECTED";
      restartOrAbortTask(node);
      break;
    case "undecided":
      node.status = "WAITING";
      requestMoreContextFromJulesVM(node);
      break;
  }
}
```

---

### **6.3. Integrating GitHub Actions Fallbacks**

If a task exceeds **Jules VM**'s capabilities, the orchestrator refers to **`agents.md`** to decide whether to trigger **GitHub Actions** or another fallback method.

For example, if **Jules VM** cannot generate a certain artifact, such as an Android APK, the orchestrator will automatically invoke a GitHub Action to build the APK.

```yaml
capabilities:
  - task: "Build Android APK"
    supported: false  # VM cannot handle this task natively
    fallback: "github_actions"  # Use GitHub Actions for this task
```

The orchestrator will then trigger the appropriate GitHub Actions workflow, as defined in the GitHub repository’s `.github` folder.

---

## **7. Integration with `agents.md` and Dynamic Updates**

Each **Jules VM**'s **capabilities** are defined in **`agents.md`**, which the orchestrator reads during workflow execution to decide whether a fallback to **GitHub Actions** is necessary. The orchestrator also has the ability to **dynamically patch** the **`agents.md`** file, allowing for real-time updates based on new capabilities, task requirements, or newly added GitHub Action workflows.

---

## **8. Conclusion**

The **Jules Workflow Orchestrator** combines powerful task orchestration with human-in-the-loop feedback and intelligent decision-making. By integrating **Telegram** for real-time feedback, **GitHub Actions** as a fallback for tasks exceeding **Jules VMs**’ capabilities, and a flexible state machine for managing task execution, the orchestrator provides a seamless and adaptive solution for managing AI-driven development workflows.

The system’s ability to dynamically adapt through **`agents.md`** updates ensures that it remains flexible and extensible as workflows grow more complex. Whether tasks are executed directly on **Jules VMs** or delegated to **GitHub Actions**, the orchestrator maintains a smooth and efficient process, providing real-time feedback to users and ensuring that workflows can adapt dynamically to changing requirements.

By leveraging **Telegram integration** and **chat-based interactions**, users can remain in control of the workflow, providing valuable feedback and approvals directly through familiar communication channels, making the entire system interactive, responsive, and user-friendly.
